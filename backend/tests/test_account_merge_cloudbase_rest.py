"""CloudBase REST replay and cross-backend merge contract tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlmodel import Session, select

from app.core.errors import MergeConsistency
from app.models.daily_log import DailyLog
from app.models.dining_memory import DiningMemory
from app.models.favorite import Favorite
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.cloudbase_rdb import RdbFilter, RdbResult
from app.repositories.cloudbase_repository import CloudBaseRepository
from app.services.account_merge_service import merge_guest_into_wechat
from tests.test_cloudbase_rest_services import MemoryRdbClient


class FailureAfterWriteMemoryRdbClient(MemoryRdbClient):
    def __init__(self, failure_table: str) -> None:
        super().__init__()
        self.failure_table = failure_table
        self.failed = False

    def update(self, table: str, values: Any, *, filters: Any) -> RdbResult:
        result = super().update(table, values, filters=filters)
        if table == self.failure_table and not self.failed:
            self.failed = True
            raise RuntimeError(f"injected response loss after {table} write")
        return result

    def delete(self, table: str, *, filters: Any) -> RdbResult:
        self.write_calls.append(
            ("delete", table, {"filters": tuple(filters)}),
        )
        return super().delete(table, filters=filters)


def _fixture_records() -> list[Any]:
    created = datetime(2026, 8, 20, 10, 0)
    return [
        User(
            id=1,
            openid="guest:equivalent-fixture",
            account_kind="guest",
            account_status="active",
            nickname="游客昵称",
            avatar_url="https://example.invalid/guest.png",
        ),
        User(
            id=2,
            openid="wechat-equivalent-fixture",
            account_kind="wechat",
            account_status="active",
            nickname="微信用户",
        ),
        RecommendationEvent(
            id=10,
            request_id="guest-request",
            user_id=1,
            event_date=date(2026, 8, 20),
            recommended_food_ids_json=[100, 101],
            primary_meal_json={"meal": "guest"},
            created_at=created,
        ),
        RecommendationEvent(
            id=11,
            request_id="formal-request",
            user_id=2,
            event_date=date(2026, 8, 21),
            recommended_food_ids_json=[101],
            primary_meal_json={"meal": "formal"},
            created_at=created,
        ),
        Favorite(id=20, user_id=1, food_id=100, created_at=created),
        Favorite(id=21, user_id=1, food_id=101, created_at=created),
        Favorite(id=22, user_id=2, food_id=101, created_at=created),
        DailyLog(
            id=30,
            user_id=1,
            log_date=date(2026, 8, 20),
            recommendation_event_id=10,
            recommended_food_ids_json=[100],
            recommended_meal_json={"meal": "unique"},
            created_at=created,
            updated_at=created,
        ),
        DailyLog(
            id=31,
            user_id=1,
            log_date=date(2026, 8, 21),
            recommendation_event_id=10,
            recommended_food_ids_json=[100, 101],
            recommended_meal_json={"meal": "guest-conflict"},
            chosen_food_ids_json=[100],
            chosen_meal_json={"meal": "guest-choice"},
            chosen_total_nutrition_json={"energy": 500},
            mood="sad",
            created_at=created,
            updated_at=created,
        ),
        DailyLog(
            id=32,
            user_id=2,
            log_date=date(2026, 8, 21),
            recommendation_event_id=11,
            mood="happy",
            created_at=created,
            updated_at=created,
        ),
        DiningMemory(
            id=40,
            user_id=1,
            shop_name="独有店",
            dish_name="独有菜",
            normalized_shop_name="独有店",
            normalized_dish_name="独有菜",
            verdict="like",
            note="独有",
            created_at=created,
            updated_at=created,
        ),
        DiningMemory(
            id=41,
            user_id=1,
            shop_name="游客店名",
            dish_name="游客菜名",
            normalized_shop_name="同店",
            normalized_dish_name="同菜",
            verdict="dislike",
            note="游客 note",
            created_at=created,
            updated_at=created,
        ),
        DiningMemory(
            id=42,
            user_id=2,
            shop_name="正式店名",
            dish_name="正式菜名",
            normalized_shop_name="同店",
            normalized_dish_name="同菜",
            verdict="like",
            note=None,
            created_at=created,
            updated_at=created,
        ),
        UserProfile(
            user_id=1,
            birthday="1990-01-02",
            gender="female",
            height_cm=165,
            weight_kg=52.5,
            forbidden_tags=["peanut"],
            constitution_type="qixu",
            constitution_scores={"qixu": 88},
            updated_at=created,
        ),
        UserProfile(
            user_id=2,
            birthday="1988-03-04",
            gender="male",
            height_cm=None,
            weight_kg=70.0,
            forbidden_tags=[],
            constitution_type=None,
            constitution_scores={},
            updated_at=created,
        ),
    ]


def _seed_sqlalchemy(session: Session) -> tuple[User, User]:
    records = _fixture_records()
    for record in records:
        session.add(record)
    session.commit()
    source = session.get(User, 1)
    target = session.get(User, 2)
    assert source is not None and target is not None
    return source, target


def _seed_rest(repository: CloudBaseRepository) -> tuple[User, User]:
    records = _fixture_records()
    for record in records:
        repository.insert(record)
    source = repository.get(User, 1)
    target = repository.get(User, 2)
    assert source is not None and target is not None
    return source, target


def _normalized_sqlalchemy(session: Session) -> dict[str, Any]:
    source = session.get(User, 1)
    target = session.get(User, 2)
    assert source is not None and target is not None
    return _normalize(
        source,
        target,
        session.exec(select(Favorite).where(Favorite.user_id == 2)).all(),
        session.exec(
            select(RecommendationEvent).where(RecommendationEvent.user_id == 2)
        ).all(),
        session.exec(select(DailyLog).where(DailyLog.user_id == 2)).all(),
        session.exec(select(DiningMemory).where(DiningMemory.user_id == 2)).all(),
        session.get(UserProfile, 2),
    )


def _normalized_rest(repository: CloudBaseRepository) -> dict[str, Any]:
    source = repository.get(User, 1)
    target = repository.get(User, 2)
    assert source is not None and target is not None
    return _normalize(
        source,
        target,
        repository.list(Favorite, filters=(RdbFilter("user_id", "eq", 2),)),
        repository.list(
            RecommendationEvent,
            filters=(RdbFilter("user_id", "eq", 2),),
        ),
        repository.list(DailyLog, filters=(RdbFilter("user_id", "eq", 2),)),
        repository.list(DiningMemory, filters=(RdbFilter("user_id", "eq", 2),)),
        repository.get(UserProfile, 2),
    )


def _normalize(
    source: User,
    target: User,
    favorites: list[Favorite],
    events: list[RecommendationEvent],
    daily_logs: list[DailyLog],
    memories: list[DiningMemory],
    profile: UserProfile | None,
) -> dict[str, Any]:
    assert profile is not None
    return {
        "source": (source.account_status, source.merged_into_user_id),
        "target_public": (target.nickname, target.avatar_url),
        "favorites": sorted((row.id, row.user_id, row.food_id) for row in favorites),
        "events": sorted(
            (
                row.id,
                row.user_id,
                row.request_id,
                row.recommended_food_ids_json,
                row.primary_meal_json,
            )
            for row in events
        ),
        "daily": sorted(
            (
                row.id,
                row.user_id,
                row.recommendation_event_id,
                row.recommended_food_ids_json,
                row.recommended_meal_json,
                row.chosen_food_ids_json,
                row.chosen_meal_json,
                row.chosen_total_nutrition_json,
                row.mood,
            )
            for row in daily_logs
        ),
        "memories": sorted(
            (
                row.id,
                row.user_id,
                row.shop_name,
                row.dish_name,
                row.verdict,
                row.note,
            )
            for row in memories
        ),
        "profile": (
            profile.user_id,
            profile.birthday,
            profile.gender,
            profile.height_cm,
            profile.weight_kg,
            profile.forbidden_tags,
            profile.constitution_type,
            profile.constitution_scores,
        ),
    }


def test_same_conflict_fixture_has_equivalent_sqlalchemy_and_rest_snapshot(
    session: Session,
) -> None:
    source, target = _seed_sqlalchemy(session)
    merge_guest_into_wechat(session, source, target)
    expected = _normalized_sqlalchemy(session)

    repository = CloudBaseRepository(MemoryRdbClient())
    rest_source, rest_target = _seed_rest(repository)
    merge_guest_into_wechat(repository, rest_source, rest_target)

    assert _normalized_rest(repository) == expected


def test_rest_final_validation_pages_past_fifty_target_daily_logs() -> None:
    repository = CloudBaseRepository(MemoryRdbClient())
    source = repository.insert(
        User(
            id=1,
            openid="guest:paged-final-scan",
            account_kind="guest",
            account_status="active",
        )
    )
    target = repository.insert(
        User(
            id=2,
            openid="wechat-paged-final-scan",
            account_kind="wechat",
            account_status="active",
        )
    )
    repository.insert(
        User(
            id=3,
            openid="unrelated-paged-user",
            account_kind="wechat",
            account_status="active",
        )
    )
    unrelated_event = repository.insert(
        RecommendationEvent(
            id=99,
            request_id="paged-unrelated-event",
            user_id=3,
            event_date=date(2026, 1, 1),
        )
    )
    for index in range(51):
        repository.insert(
            DailyLog(
                id=100 + index,
                user_id=2,
                log_date=date(2026, 1, 1) + timedelta(days=index),
                recommendation_event_id=(unrelated_event.id if index == 50 else None),
            )
        )

    with pytest.raises(MergeConsistency, match="不属于正式账户"):
        merge_guest_into_wechat(repository, source, target)

    stored_source = repository.get(User, source.id)
    assert stored_source is not None
    assert stored_source.account_status == "merging"


@pytest.mark.parametrize(
    "failure_table",
    [
        "recommendation_events",
        "daily_logs",
        "favorites",
        "dining_memories",
        "user_profiles",
    ],
)
def test_rest_replay_converges_after_each_step_loses_a_success_response(
    failure_table: str,
) -> None:
    client = FailureAfterWriteMemoryRdbClient(failure_table)
    repository = CloudBaseRepository(client)
    source, target = _seed_rest(repository)

    with pytest.raises(RuntimeError, match="injected response loss"):
        merge_guest_into_wechat(repository, source, target)

    interrupted_source = repository.get(User, source.id)
    assert interrupted_source is not None
    assert interrupted_source.account_status == "merging"

    merge_guest_into_wechat(repository, interrupted_source, target)

    completed_source = repository.get(User, source.id)
    assert completed_source is not None
    assert completed_source.account_status == "merged"
    for model in (Favorite, RecommendationEvent, DailyLog, DiningMemory):
        assert repository.first(
            model,
            filters=(RdbFilter("user_id", "eq", source.id),),
        ) is None
    assert repository.get(UserProfile, source.id) is None

    for method, table, payload in client.write_calls:
        if method == "update" and payload["values"].get("user_id") == target.id:
            filter_fields = {item.field for item in payload["filters"]}
            assert filter_fields >= {"id", "user_id"}, table
            assert RdbFilter("user_id", "eq", source.id) in payload["filters"]
        if method == "delete" and table != "user_profiles":
            filter_fields = {item.field for item in payload["filters"]}
            assert filter_fields >= {"id", "user_id"}, table
            assert RdbFilter("user_id", "eq", source.id) in payload["filters"]
