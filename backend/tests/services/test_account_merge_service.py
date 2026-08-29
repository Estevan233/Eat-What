"""SQLAlchemy contract tests for guest-to-WeChat account merging."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session, select

from app.core.errors import MergeConsistency, MergeTargetConflict
from app.models.daily_log import DailyLog
from app.models.dining_memory import DiningMemory
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services import account_merge_service
from app.services.account_merge_service import MergeSummary, merge_guest_into_wechat


def _persist_users(session: Session, *, target_nickname: str = "微信用户") -> tuple[User, User]:
    source = User(
        openid="guest:test-account-merge",
        account_kind="guest",
        account_status="active",
        nickname="小馋猫",
        avatar_url="https://example.invalid/guest.png",
    )
    target = User(
        openid="wechat-account-merge",
        account_kind="wechat",
        account_status="active",
        nickname=target_nickname,
    )
    session.add(source)
    session.add(target)
    session.commit()
    session.refresh(source)
    session.refresh(target)
    return source, target


def _persist_food(session: Session, name: str) -> Food:
    food = Food(
        name=name,
        category="staple",
        nature="neutral",
        cooking_method="boil",
    )
    session.add(food)
    session.commit()
    session.refresh(food)
    return food


def test_empty_merge_marks_tombstone_and_fills_public_placeholders(session: Session) -> None:
    source, target = _persist_users(session)

    summary = merge_guest_into_wechat(session, source, target)

    assert summary == MergeSummary()
    stored_source = session.exec(select(User).where(User.id == source.id)).one()
    stored_target = session.exec(select(User).where(User.id == target.id)).one()
    assert stored_source.account_status == "merged"
    assert stored_source.merged_into_user_id == target.id
    assert stored_source.merge_started_at is not None
    assert stored_source.merged_at is not None
    assert stored_target.nickname == "小馋猫"
    assert stored_target.avatar_url == "https://example.invalid/guest.png"


def test_completed_merge_replay_is_idempotent(session: Session) -> None:
    source, target = _persist_users(session)
    first = merge_guest_into_wechat(session, source, target)
    completed_at = source.merged_at

    second = merge_guest_into_wechat(session, source, target)

    assert first == second == MergeSummary()
    assert source.merged_at == completed_at


def test_merge_rejects_a_different_bound_target(session: Session) -> None:
    source, target = _persist_users(session)
    merge_guest_into_wechat(session, source, target)
    other_target = User(
        openid="other-wechat-account",
        account_kind="wechat",
        account_status="active",
    )
    session.add(other_target)
    session.commit()
    session.refresh(other_target)

    with pytest.raises(MergeTargetConflict) as raised:
        merge_guest_into_wechat(session, source, other_target)

    assert raised.value.status_code == 409
    assert raised.value.code == "MERGE_TARGET_CONFLICT"
    assert source.merged_into_user_id == target.id


def test_favorites_move_unique_rows_and_keep_formal_duplicates(session: Session) -> None:
    source, target = _persist_users(session)
    unique_food = _persist_food(session, "游客独有菜")
    shared_food = _persist_food(session, "双方都收藏")
    source_unique = Favorite(user_id=source.id, food_id=unique_food.id)
    source_duplicate = Favorite(user_id=source.id, food_id=shared_food.id)
    target_duplicate = Favorite(user_id=target.id, food_id=shared_food.id)
    session.add(source_unique)
    session.add(source_duplicate)
    session.add(target_duplicate)
    session.commit()
    session.refresh(source_unique)
    session.refresh(target_duplicate)
    source_unique_id = source_unique.id
    source_unique_created_at = source_unique.created_at
    target_duplicate_id = target_duplicate.id

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.favorites_moved == 1
    assert summary.favorites_deleted == 1
    assert session.exec(select(Favorite).where(Favorite.user_id == source.id)).all() == []
    target_rows = session.exec(
        select(Favorite).where(Favorite.user_id == target.id).order_by(Favorite.id)
    ).all()
    assert [(row.id, row.food_id) for row in target_rows] == [
        (source_unique_id, unique_food.id),
        (target_duplicate_id, shared_food.id),
    ]
    assert target_rows[0].created_at == source_unique_created_at


def test_recommendation_events_only_change_owner(session: Session) -> None:
    source, target = _persist_users(session)
    created_at = datetime(2026, 8, 20, 12, 30)
    event = RecommendationEvent(
        request_id="merge-event-request",
        user_id=source.id,
        event_date=date(2026, 8, 20),
        recommended_food_ids_json=[9, 7, 5],
        primary_food_ids_json=[9, 7],
        substitution_options_json=[{"primary_food_id": 9, "substitute_food_ids": [3]}],
        primary_meal_json={"items": [{"food_id": 9}]},
        mood="happy",
        summary_json={"reason": "snapshot"},
        created_at=created_at,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    event_id = event.id

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.recommendation_events_moved == 1
    moved = session.exec(
        select(RecommendationEvent).where(RecommendationEvent.id == event_id)
    ).one()
    assert moved.user_id == target.id
    assert moved.request_id == "merge-event-request"
    assert moved.recommended_food_ids_json == [9, 7, 5]
    assert moved.primary_meal_json == {"items": [{"food_id": 9}]}
    assert moved.summary_json == {"reason": "snapshot"}
    assert moved.created_at == created_at


def test_daily_logs_move_unique_and_merge_conflicts_by_whole_group(session: Session) -> None:
    source, target = _persist_users(session)
    source_unique_event = RecommendationEvent(
        request_id="daily-source-unique-event",
        user_id=source.id,
        event_date=date(2026, 8, 21),
    )
    source_conflict_event = RecommendationEvent(
        request_id="daily-source-conflict-event",
        user_id=source.id,
        event_date=date(2026, 8, 22),
    )
    target_conflict_event = RecommendationEvent(
        request_id="daily-target-conflict-event",
        user_id=target.id,
        event_date=date(2026, 8, 22),
    )
    session.add(source_unique_event)
    session.add(source_conflict_event)
    session.add(target_conflict_event)
    session.commit()
    for event in (source_unique_event, source_conflict_event, target_conflict_event):
        session.refresh(event)

    source_unique = DailyLog(
        user_id=source.id,
        log_date=date(2026, 8, 21),
        recommendation_event_id=source_unique_event.id,
        recommended_food_ids_json=[1, 2, 3],
        recommended_meal_json={"meal": "source-unique"},
        mood="sad",
    )
    source_conflict = DailyLog(
        user_id=source.id,
        log_date=date(2026, 8, 22),
        recommendation_event_id=source_conflict_event.id,
        recommended_food_ids_json=[4, 5, 6],
        recommended_meal_json={"meal": "source-conflict"},
        chosen_food_ids_json=[5],
        chosen_meal_json={"meal": "guest-choice"},
        chosen_total_nutrition_json={"energy": 555},
        mood="sad",
        activity_level="high",
        dining_mode="delivery",
        audience="family",
        party_size=4,
    )
    target_conflict = DailyLog(
        user_id=target.id,
        log_date=date(2026, 8, 22),
        recommendation_event_id=target_conflict_event.id,
        recommended_food_ids_json=[],
        recommended_meal_json=None,
        chosen_food_ids_json=[],
        chosen_meal_json=None,
        chosen_total_nutrition_json=None,
        mood="happy",
        activity_level="low",
        dining_mode="cook",
        audience="personal",
        party_size=1,
    )
    session.add(source_unique)
    session.add(source_conflict)
    session.add(target_conflict)
    session.commit()
    session.refresh(source_unique)
    session.refresh(target_conflict)
    source_unique_id = source_unique.id
    target_conflict_id = target_conflict.id

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.daily_logs_moved == 1
    assert summary.daily_logs_merged == 1
    assert session.exec(select(DailyLog).where(DailyLog.user_id == source.id)).all() == []
    unique = session.exec(select(DailyLog).where(DailyLog.id == source_unique_id)).one()
    assert unique.user_id == target.id
    assert unique.recommendation_event_id == source_unique_event.id
    assert unique.recommended_meal_json == {"meal": "source-unique"}
    conflict = session.exec(select(DailyLog).where(DailyLog.id == target_conflict_id)).one()
    assert conflict.recommendation_event_id == target_conflict_event.id
    assert conflict.recommended_food_ids_json == []
    assert conflict.recommended_meal_json is None
    assert conflict.chosen_food_ids_json == [5]
    assert conflict.chosen_meal_json == {"meal": "guest-choice"}
    assert conflict.chosen_total_nutrition_json == {"energy": 555}
    assert conflict.mood == "happy"
    assert conflict.activity_level == "low"
    assert conflict.dining_mode == "cook"
    assert conflict.audience == "personal"
    assert conflict.party_size == 1


def test_dining_memories_move_unique_and_only_fill_empty_formal_note(session: Session) -> None:
    source, target = _persist_users(session)
    unique_created_at = datetime(2026, 8, 17, 8, 0)
    formal_created_at = datetime(2026, 8, 18, 9, 0)
    source_unique = DiningMemory(
        user_id=source.id,
        shop_name="游客小店",
        dish_name="游客小菜",
        normalized_shop_name="游客小店",
        normalized_dish_name="游客小菜",
        verdict="like",
        note="独有记忆",
        created_at=unique_created_at,
    )
    source_conflict = DiningMemory(
        user_id=source.id,
        shop_name="游客写法",
        dish_name="游客菜名",
        normalized_shop_name="同一家店",
        normalized_dish_name="同一道菜",
        verdict="dislike",
        note="游客补充说明",
    )
    target_conflict = DiningMemory(
        user_id=target.id,
        shop_name="正式店名",
        dish_name="正式菜名",
        normalized_shop_name="同一家店",
        normalized_dish_name="同一道菜",
        verdict="like",
        note="   ",
        created_at=formal_created_at,
    )
    session.add(source_unique)
    session.add(source_conflict)
    session.add(target_conflict)
    session.commit()
    session.refresh(source_unique)
    session.refresh(target_conflict)
    source_unique_id = source_unique.id
    target_conflict_id = target_conflict.id

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.dining_memories_moved == 1
    assert summary.dining_memories_merged == 1
    assert session.exec(
        select(DiningMemory).where(DiningMemory.user_id == source.id)
    ).all() == []
    unique = session.exec(
        select(DiningMemory).where(DiningMemory.id == source_unique_id)
    ).one()
    assert unique.user_id == target.id
    assert unique.created_at == unique_created_at
    conflict = session.exec(
        select(DiningMemory).where(DiningMemory.id == target_conflict_id)
    ).one()
    assert conflict.shop_name == "正式店名"
    assert conflict.dish_name == "正式菜名"
    assert conflict.verdict == "like"
    assert conflict.note == "游客补充说明"
    assert conflict.created_at == formal_created_at


def test_profile_moves_to_target_when_formal_profile_is_missing(session: Session) -> None:
    source, target = _persist_users(session)
    updated_at = datetime(2026, 8, 16, 7, 30)
    source_profile = UserProfile(
        user_id=source.id,
        birthday="1990-01-02",
        gender="female",
        height_cm=165,
        weight_kg=52.5,
        forbidden_tags=["peanut"],
        constitution_type="qixu",
        constitution_scores={"qixu": 88},
        updated_at=updated_at,
    )
    session.add(source_profile)
    session.commit()

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.profiles_moved == 1
    assert session.get(UserProfile, source.id) is None
    moved = session.get(UserProfile, target.id)
    assert moved is not None
    assert moved.birthday == "1990-01-02"
    assert moved.gender == "female"
    assert moved.height_cm == 165
    assert moved.weight_kg == 52.5
    assert moved.forbidden_tags == ["peanut"]
    assert moved.constitution_type == "qixu"
    assert moved.constitution_scores == {"qixu": 88}
    assert moved.updated_at == updated_at


def test_profile_conflict_preserves_formal_fields_and_only_fills_none(session: Session) -> None:
    source, target = _persist_users(session)
    source_profile = UserProfile(
        user_id=source.id,
        birthday="1990-01-02",
        gender="female",
        height_cm=165,
        weight_kg=52.5,
        forbidden_tags=["peanut"],
        constitution_type="qixu",
        constitution_scores={"qixu": 88},
    )
    target_profile = UserProfile(
        user_id=target.id,
        birthday="1988-03-04",
        gender="male",
        height_cm=None,
        weight_kg=70.0,
        forbidden_tags=[],
        constitution_type=None,
        constitution_scores={},
    )
    session.add(source_profile)
    session.add(target_profile)
    session.commit()

    summary = merge_guest_into_wechat(session, source, target)

    assert summary.profiles_merged == 1
    assert session.get(UserProfile, source.id) is None
    merged = session.get(UserProfile, target.id)
    assert merged is not None
    assert merged.birthday == "1988-03-04"
    assert merged.gender == "male"
    assert merged.forbidden_tags == []
    assert merged.height_cm == 165
    assert merged.weight_kg == 70.0
    assert merged.constitution_type == "qixu"
    assert merged.constitution_scores == {}


def test_merge_failure_rolls_back_data_but_keeps_source_merging(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _persist_users(session)

    def fail_daily_merge(*args: object, **kwargs: object) -> tuple[int, int]:
        raise RuntimeError("injected daily merge failure")

    monkeypatch.setattr(
        account_merge_service,
        "_merge_daily_logs_sqlalchemy",
        fail_daily_merge,
    )

    with pytest.raises(RuntimeError, match="injected daily merge failure"):
        merge_guest_into_wechat(session, source, target)

    assert session.in_transaction() is False
    session.expire_all()
    stored_source = session.get(User, source.id)
    stored_target = session.get(User, target.id)
    assert stored_source is not None
    assert stored_source.account_status == "merging"
    assert stored_source.merged_into_user_id == target.id
    assert stored_source.merged_at is None
    assert stored_target is not None
    assert stored_target.nickname == "微信用户"
    assert stored_target.avatar_url is None


def test_daily_log_with_cross_user_event_fails_consistency_and_stays_merging(
    session: Session,
) -> None:
    source, target = _persist_users(session)
    unrelated = User(
        openid="unrelated-wechat",
        account_kind="wechat",
        account_status="active",
    )
    session.add(unrelated)
    session.commit()
    session.refresh(unrelated)
    unrelated_event = RecommendationEvent(
        request_id="unrelated-event",
        user_id=unrelated.id,
        event_date=date(2026, 8, 23),
    )
    session.add(unrelated_event)
    session.commit()
    session.refresh(unrelated_event)
    source_daily = DailyLog(
        user_id=source.id,
        log_date=date(2026, 8, 23),
        recommendation_event_id=unrelated_event.id,
    )
    session.add(source_daily)
    session.commit()

    with pytest.raises(MergeConsistency) as raised:
        merge_guest_into_wechat(session, source, target)

    assert raised.value.code == "MERGE_DATA_CONFLICT"
    assert raised.value.status_code == 409
    session.expire_all()
    assert session.get(User, source.id).account_status == "merging"
    assert session.exec(select(DailyLog).where(DailyLog.user_id == source.id)).one()


def test_final_residual_scan_prevents_merged_state(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _persist_users(session)
    source_profile = UserProfile(
        user_id=source.id,
        birthday="1990-01-02",
        gender="female",
    )
    session.add(source_profile)
    session.commit()

    def skip_profile_merge(*args: object, **kwargs: object) -> tuple[int, int]:
        return 0, 0

    monkeypatch.setattr(
        account_merge_service,
        "_merge_profile_sqlalchemy",
        skip_profile_merge,
    )

    with pytest.raises(MergeConsistency, match="仍有游客数据"):
        merge_guest_into_wechat(session, source, target)

    session.expire_all()
    assert session.get(User, source.id).account_status == "merging"
    assert session.get(UserProfile, source.id) is not None
