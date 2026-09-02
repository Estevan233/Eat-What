"""Deterministic guest-to-WeChat account merge service."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

from sqlmodel import Session, SQLModel, col, select

from app.core.errors import MergeConsistency, MergeTargetConflict
from app.models.daily_log import DailyLog
from app.models.dining_memory import DiningMemory
from app.models.favorite import Favorite
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.cloudbase_rdb import RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import (
    CloudBaseRepository,
    DatabaseSession,
    is_cloudbase_repository,
)

ModelT = TypeVar("ModelT", bound=SQLModel)


@dataclass(frozen=True)
class MergeSummary:
    """Internal-only counters for merge observability."""

    favorites_moved: int = 0
    favorites_deleted: int = 0
    recommendation_events_moved: int = 0
    daily_logs_moved: int = 0
    daily_logs_merged: int = 0
    dining_memories_moved: int = 0
    dining_memories_merged: int = 0
    profiles_moved: int = 0
    profiles_merged: int = 0


_FORMAL_NICKNAME_PLACEHOLDERS = frozenset({"微信用户", "用户"})
_GUEST_NICKNAME_PLACEHOLDERS = frozenset({"", "游客", "微信用户", "用户"})


def _merge_public_profile(source: User, target: User) -> None:
    if (
        target.nickname.strip() in _FORMAL_NICKNAME_PLACEHOLDERS
        and source.nickname.strip() not in _GUEST_NICKNAME_PLACEHOLDERS
    ):
        target.nickname = source.nickname
    if not target.avatar_url and source.avatar_url:
        target.avatar_url = source.avatar_url
    target.updated_at = datetime.utcnow()


def _merge_favorites_sqlalchemy(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    deleted = 0
    source_rows = session.exec(
        select(Favorite)
        .where(Favorite.user_id == source_id)
        .order_by(col(Favorite.id))
    ).all()
    for source_row in source_rows:
        target_row = session.exec(
            select(Favorite).where(
                Favorite.user_id == target_id,
                Favorite.food_id == source_row.food_id,
            )
        ).first()
        if target_row is not None:
            session.delete(source_row)
            deleted += 1
            continue
        source_row.user_id = target_id
        session.add(source_row)
        moved += 1
    return moved, deleted


def _merge_recommendation_events_sqlalchemy(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> int:
    source_rows = session.exec(
        select(RecommendationEvent)
        .where(RecommendationEvent.user_id == source_id)
        .order_by(col(RecommendationEvent.id))
    ).all()
    for source_row in source_rows:
        source_row.user_id = target_id
        session.add(source_row)
    return len(source_rows)


def _is_empty_snapshot_value(value: object) -> bool:
    return value is None or value == [] or value == {}


def _merge_daily_snapshot_groups(source: DailyLog, target: DailyLog) -> None:
    target_recommendation_group = (
        target.recommendation_event_id,
        target.recommended_food_ids_json,
        target.recommended_meal_json,
    )
    if all(_is_empty_snapshot_value(value) for value in target_recommendation_group):
        target.recommendation_event_id = source.recommendation_event_id
        target.recommended_food_ids_json = list(source.recommended_food_ids_json)
        target.recommended_meal_json = source.recommended_meal_json

    target_choice_group = (
        target.chosen_food_ids_json,
        target.chosen_meal_json,
        target.chosen_total_nutrition_json,
    )
    if all(_is_empty_snapshot_value(value) for value in target_choice_group):
        target.chosen_food_ids_json = list(source.chosen_food_ids_json)
        target.chosen_meal_json = source.chosen_meal_json
        target.chosen_total_nutrition_json = source.chosen_total_nutrition_json


def _require_target_owned_event_sqlalchemy(
    session: Session,
    *,
    event_id: int | None,
    target_id: int,
) -> None:
    if event_id is None:
        return
    event = session.get(RecommendationEvent, event_id)
    if event is None or event.user_id != target_id:
        raise MergeConsistency("日报引用的推荐事件不属于正式账户")


def _merge_daily_logs_sqlalchemy(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    merged = 0
    source_rows = session.exec(
        select(DailyLog)
        .where(DailyLog.user_id == source_id)
        .order_by(col(DailyLog.id))
    ).all()
    for source_row in source_rows:
        _require_target_owned_event_sqlalchemy(
            session,
            event_id=source_row.recommendation_event_id,
            target_id=target_id,
        )
        target_row = session.exec(
            select(DailyLog).where(
                DailyLog.user_id == target_id,
                DailyLog.log_date == source_row.log_date,
                DailyLog.meal_slot == source_row.meal_slot,
                DailyLog.source == source_row.source,
            )
        ).first()
        if target_row is None:
            source_row.user_id = target_id
            session.add(source_row)
            moved += 1
            continue
        _require_target_owned_event_sqlalchemy(
            session,
            event_id=target_row.recommendation_event_id,
            target_id=target_id,
        )
        _merge_daily_snapshot_groups(source_row, target_row)
        target_row.updated_at = datetime.utcnow()
        session.add(target_row)
        session.delete(source_row)
        merged += 1
    return moved, merged


def _merge_dining_memories_sqlalchemy(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    merged = 0
    source_rows = session.exec(
        select(DiningMemory)
        .where(DiningMemory.user_id == source_id)
        .order_by(col(DiningMemory.id))
    ).all()
    for source_row in source_rows:
        target_row = session.exec(
            select(DiningMemory).where(
                DiningMemory.user_id == target_id,
                DiningMemory.normalized_shop_name
                == source_row.normalized_shop_name,
                DiningMemory.normalized_dish_name
                == source_row.normalized_dish_name,
            )
        ).first()
        if target_row is None:
            source_row.user_id = target_id
            session.add(source_row)
            moved += 1
            continue
        if (target_row.note is None or not target_row.note.strip()) and source_row.note:
            target_row.note = source_row.note
            target_row.updated_at = datetime.utcnow()
            session.add(target_row)
        session.delete(source_row)
        merged += 1
    return moved, merged


def _merge_profile_sqlalchemy(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    source_profile = session.get(UserProfile, source_id)
    if source_profile is None:
        return 0, 0
    target_profile = session.get(UserProfile, target_id)
    if target_profile is not None:
        changed = False
        for field_name in (
            "height_cm",
            "weight_kg",
            "constitution_type",
            "constitution_scores",
        ):
            if getattr(target_profile, field_name) is None:
                setattr(target_profile, field_name, getattr(source_profile, field_name))
                changed = True
        if changed:
            target_profile.updated_at = datetime.utcnow()
            session.add(target_profile)
        session.delete(source_profile)
        return 0, 1
    values = source_profile.model_dump()
    values["user_id"] = target_id
    session.add(UserProfile.model_validate(values))
    session.delete(source_profile)
    return 1, 0


def _assert_sqlalchemy_merge_consistent(
    session: Session,
    *,
    source_id: int,
    target_id: int,
) -> None:
    session.flush()
    residuals = (
        session.exec(
            select(Favorite.id).where(Favorite.user_id == source_id).limit(1)
        ).first(),
        session.exec(
            select(RecommendationEvent.id)
            .where(RecommendationEvent.user_id == source_id)
            .limit(1)
        ).first(),
        session.exec(
            select(DailyLog.id).where(DailyLog.user_id == source_id).limit(1)
        ).first(),
        session.exec(
            select(DiningMemory.id)
            .where(DiningMemory.user_id == source_id)
            .limit(1)
        ).first(),
        session.exec(
            select(UserProfile.user_id)
            .where(UserProfile.user_id == source_id)
            .limit(1)
        ).first(),
    )
    if any(value is not None for value in residuals):
        raise MergeConsistency("合并完成检查仍有游客数据")

    target_daily_logs = session.exec(
        select(DailyLog).where(DailyLog.user_id == target_id)
    ).all()
    for daily_log in target_daily_logs:
        _require_target_owned_event_sqlalchemy(
            session,
            event_id=daily_log.recommendation_event_id,
            target_id=target_id,
        )


def _cloudbase_source_batches(
    repository: CloudBaseRepository,
    model: type[ModelT],
    *,
    source_id: int,
    primary_key: str = "id",
    batch_size: int = 50,
) -> Iterator[list[ModelT]]:
    """Yield stable source-owned batches; processed rows leave the source set."""
    while True:
        rows = repository.list(
            model,
            filters=(RdbFilter("user_id", "eq", source_id),),
            order=(RdbOrder(primary_key, "asc"),),
            limit=batch_size,
        )
        if not rows:
            return
        yield rows


def _cloudbase_ordered_pages(
    repository: CloudBaseRepository,
    model: type[ModelT],
    *,
    filters: Sequence[RdbFilter],
    primary_key: str = "id",
    batch_size: int = 50,
) -> Iterator[list[ModelT]]:
    last_primary_key: int | None = None
    while True:
        page_filters = list(filters)
        if last_primary_key is not None:
            page_filters.append(RdbFilter(primary_key, "gt", last_primary_key))
        rows = repository.list(
            model,
            filters=tuple(page_filters),
            order=(RdbOrder(primary_key, "asc"),),
            limit=batch_size,
        )
        if not rows:
            return
        yield rows
        current_primary_key = getattr(rows[-1], primary_key, None)
        if not isinstance(current_primary_key, int):
            raise MergeConsistency("REST 分页记录缺少整数主键")
        last_primary_key = current_primary_key


def _cloudbase_guarded_owner_update(
    repository: CloudBaseRepository,
    model: type[ModelT],
    *,
    row_id: int,
    source_id: int,
    target_id: int,
) -> bool:
    updated = repository.update_fields(
        model,
        values={"user_id": target_id},
        filters=(
            RdbFilter("id", "eq", row_id),
            RdbFilter("user_id", "eq", source_id),
        ),
    )
    if updated is not None:
        return True
    current = repository.get(model, row_id)
    if current is not None and getattr(current, "user_id", None) == target_id:
        return False
    raise MergeConsistency("条件迁移返回零行且记录未归入正式账户")


def _cloudbase_guarded_delete(
    repository: CloudBaseRepository,
    model: type[ModelT],
    *,
    row_id: int,
    source_id: int,
) -> bool:
    deleted = repository.delete(
        model,
        filters=(
            RdbFilter("id", "eq", row_id),
            RdbFilter("user_id", "eq", source_id),
        ),
    )
    if deleted:
        return True
    current = repository.get(model, row_id)
    if current is None or getattr(current, "user_id", None) != source_id:
        return False
    raise MergeConsistency("条件删除返回零行且游客记录仍存在")


def _cloudbase_update_target_fields(
    repository: CloudBaseRepository,
    model: type[ModelT],
    *,
    row_id: int,
    target_id: int,
    values: dict[str, object],
) -> None:
    if not values:
        return
    updated = repository.update_fields(
        model,
        values=values,
        filters=(
            RdbFilter("id", "eq", row_id),
            RdbFilter("user_id", "eq", target_id),
        ),
    )
    if updated is not None:
        return
    current = repository.get(model, row_id)
    if current is not None and all(
        getattr(current, field_name) == value
        for field_name, value in values.items()
    ):
        return
    raise MergeConsistency("正式记录条件更新未收敛")


def _require_target_owned_event_cloudbase(
    repository: CloudBaseRepository,
    *,
    event_id: int | None,
    target_id: int,
) -> None:
    if event_id is None:
        return
    event = repository.get(RecommendationEvent, event_id)
    if event is None or event.user_id != target_id:
        raise MergeConsistency("日报引用的推荐事件不属于正式账户")


def _merge_recommendation_events_cloudbase(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> int:
    moved = 0
    for batch in _cloudbase_source_batches(
        repository,
        RecommendationEvent,
        source_id=source_id,
    ):
        for source_row in batch:
            if source_row.id is None:
                raise MergeConsistency("推荐事件缺少主键")
            request_rows = repository.list(
                RecommendationEvent,
                filters=(RdbFilter("request_id", "eq", source_row.request_id),),
                order=(RdbOrder("id", "asc"),),
                limit=2,
            )
            if len(request_rows) != 1 or request_rows[0].id != source_row.id:
                raise MergeConsistency("推荐事件 request_id 冲突")
            if _cloudbase_guarded_owner_update(
                repository,
                RecommendationEvent,
                row_id=source_row.id,
                source_id=source_id,
                target_id=target_id,
            ):
                moved += 1
    return moved


def _merge_daily_logs_cloudbase(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    merged = 0
    for batch in _cloudbase_source_batches(
        repository,
        DailyLog,
        source_id=source_id,
    ):
        for source_row in batch:
            if source_row.id is None:
                raise MergeConsistency("日报缺少主键")
            _require_target_owned_event_cloudbase(
                repository,
                event_id=source_row.recommendation_event_id,
                target_id=target_id,
            )
            target_row = repository.first(
                DailyLog,
                filters=(
                    RdbFilter("user_id", "eq", target_id),
                    RdbFilter("log_date", "eq", source_row.log_date),
                    RdbFilter("meal_slot", "eq", source_row.meal_slot),
                    RdbFilter("source", "eq", source_row.source),
                ),
            )
            if target_row is None:
                if _cloudbase_guarded_owner_update(
                    repository,
                    DailyLog,
                    row_id=source_row.id,
                    source_id=source_id,
                    target_id=target_id,
                ):
                    moved += 1
                continue
            if target_row.id is None:
                raise MergeConsistency("正式日报缺少主键")
            _require_target_owned_event_cloudbase(
                repository,
                event_id=target_row.recommendation_event_id,
                target_id=target_id,
            )
            before = (
                target_row.recommendation_event_id,
                target_row.recommended_food_ids_json,
                target_row.recommended_meal_json,
                target_row.chosen_food_ids_json,
                target_row.chosen_meal_json,
                target_row.chosen_total_nutrition_json,
            )
            _merge_daily_snapshot_groups(source_row, target_row)
            after = (
                target_row.recommendation_event_id,
                target_row.recommended_food_ids_json,
                target_row.recommended_meal_json,
                target_row.chosen_food_ids_json,
                target_row.chosen_meal_json,
                target_row.chosen_total_nutrition_json,
            )
            if after != before:
                _cloudbase_update_target_fields(
                    repository,
                    DailyLog,
                    row_id=target_row.id,
                    target_id=target_id,
                    values={
                        "recommendation_event_id": target_row.recommendation_event_id,
                        "recommended_food_ids_json": target_row.recommended_food_ids_json,
                        "recommended_meal_json": target_row.recommended_meal_json,
                        "chosen_food_ids_json": target_row.chosen_food_ids_json,
                        "chosen_meal_json": target_row.chosen_meal_json,
                        "chosen_total_nutrition_json": (
                            target_row.chosen_total_nutrition_json
                        ),
                        "updated_at": datetime.utcnow(),
                    },
                )
            _cloudbase_guarded_delete(
                repository,
                DailyLog,
                row_id=source_row.id,
                source_id=source_id,
            )
            merged += 1
    return moved, merged


def _merge_favorites_cloudbase(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    deleted = 0
    for batch in _cloudbase_source_batches(
        repository,
        Favorite,
        source_id=source_id,
    ):
        for source_row in batch:
            if source_row.id is None:
                raise MergeConsistency("收藏缺少主键")
            target_row = repository.first(
                Favorite,
                filters=(
                    RdbFilter("user_id", "eq", target_id),
                    RdbFilter("food_id", "eq", source_row.food_id),
                ),
            )
            if target_row is not None:
                _cloudbase_guarded_delete(
                    repository,
                    Favorite,
                    row_id=source_row.id,
                    source_id=source_id,
                )
                deleted += 1
                continue
            if _cloudbase_guarded_owner_update(
                repository,
                Favorite,
                row_id=source_row.id,
                source_id=source_id,
                target_id=target_id,
            ):
                moved += 1
    return moved, deleted


def _merge_dining_memories_cloudbase(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    moved = 0
    merged = 0
    for batch in _cloudbase_source_batches(
        repository,
        DiningMemory,
        source_id=source_id,
    ):
        for source_row in batch:
            if source_row.id is None:
                raise MergeConsistency("外食记忆缺少主键")
            target_row = repository.first(
                DiningMemory,
                filters=(
                    RdbFilter("user_id", "eq", target_id),
                    RdbFilter(
                        "normalized_shop_name",
                        "eq",
                        source_row.normalized_shop_name,
                    ),
                    RdbFilter(
                        "normalized_dish_name",
                        "eq",
                        source_row.normalized_dish_name,
                    ),
                ),
            )
            if target_row is None:
                if _cloudbase_guarded_owner_update(
                    repository,
                    DiningMemory,
                    row_id=source_row.id,
                    source_id=source_id,
                    target_id=target_id,
                ):
                    moved += 1
                continue
            if target_row.id is None:
                raise MergeConsistency("正式外食记忆缺少主键")
            if (target_row.note is None or not target_row.note.strip()) and source_row.note:
                _cloudbase_update_target_fields(
                    repository,
                    DiningMemory,
                    row_id=target_row.id,
                    target_id=target_id,
                    values={
                        "note": source_row.note,
                        "updated_at": datetime.utcnow(),
                    },
                )
            _cloudbase_guarded_delete(
                repository,
                DiningMemory,
                row_id=source_row.id,
                source_id=source_id,
            )
            merged += 1
    return moved, merged


def _merge_profile_cloudbase(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> tuple[int, int]:
    source_profile = repository.get(UserProfile, source_id)
    if source_profile is None:
        return 0, 0
    target_profile = repository.get(UserProfile, target_id)
    if target_profile is None:
        values = source_profile.model_dump()
        values["user_id"] = target_id
        repository.insert(UserProfile.model_validate(values))
        repository.delete(
            UserProfile,
            filters=(RdbFilter("user_id", "eq", source_id),),
        )
        return 1, 0

    patch: dict[str, object] = {}
    for field_name in (
        "height_cm",
        "weight_kg",
        "constitution_type",
        "constitution_scores",
    ):
        if getattr(target_profile, field_name) is None:
            patch[field_name] = getattr(source_profile, field_name)
    if patch:
        patch["updated_at"] = datetime.utcnow()
        updated = repository.update_fields(
            UserProfile,
            values=patch,
            filters=(RdbFilter("user_id", "eq", target_id),),
        )
        if updated is None:
            raise MergeConsistency("正式档案条件更新未收敛")
    repository.delete(
        UserProfile,
        filters=(RdbFilter("user_id", "eq", source_id),),
    )
    return 0, 1


def _assert_cloudbase_merge_consistent(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> None:
    residuals = (
        repository.first(Favorite, filters=(RdbFilter("user_id", "eq", source_id),)),
        repository.first(
            RecommendationEvent,
            filters=(RdbFilter("user_id", "eq", source_id),),
        ),
        repository.first(DailyLog, filters=(RdbFilter("user_id", "eq", source_id),)),
        repository.first(
            DiningMemory,
            filters=(RdbFilter("user_id", "eq", source_id),),
        ),
        repository.get(UserProfile, source_id),
    )
    if any(value is not None for value in residuals):
        raise MergeConsistency(
            "合并完成检查仍有游客数据",
            status_code=500,
        )
    for batch in _cloudbase_ordered_pages(
        repository,
        DailyLog,
        filters=(RdbFilter("user_id", "eq", target_id),),
    ):
        for daily_log in batch:
            _require_target_owned_event_cloudbase(
                repository,
                event_id=daily_log.recommendation_event_id,
                target_id=target_id,
            )


def _prepare_cloudbase_merge(
    repository: CloudBaseRepository,
    source: User,
    target: User,
) -> tuple[User, User]:
    if source.id is None or target.id is None:
        raise ValueError("source and target must be persisted")
    current_source = repository.get(User, source.id)
    current_target = repository.get(User, target.id)
    if current_source is None or current_target is None:
        raise MergeConsistency("合并账户不存在")
    if current_source.account_kind != "guest":
        raise ValueError("merge source must be a guest")
    if current_target.account_kind != "wechat" or current_target.account_status != "active":
        raise ValueError("merge target must be an active WeChat user")
    if (
        current_source.merged_into_user_id is not None
        and current_source.merged_into_user_id != current_target.id
    ):
        raise MergeTargetConflict
    if current_source.account_status == "active":
        transitioned = repository.update_fields(
            User,
            values={
                "account_status": "merging",
                "merged_into_user_id": current_target.id,
                "merge_started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
            filters=(
                RdbFilter("id", "eq", current_source.id),
                RdbFilter("account_kind", "eq", "guest"),
                RdbFilter("account_status", "eq", "active"),
            ),
        )
        current_source = transitioned or repository.get(User, current_source.id)
        if current_source is None:
            raise MergeConsistency("游客合并状态丢失")
        if current_source.merged_into_user_id != current_target.id:
            raise MergeTargetConflict
    if current_source.account_status not in {"merging", "merged"}:
        raise MergeConsistency("游客账户不在可恢复的合并状态")
    return current_source, current_target


def _update_cloudbase_public_profile(
    repository: CloudBaseRepository,
    source: User,
    target: User,
) -> None:
    before_public = (target.nickname, target.avatar_url)
    _merge_public_profile(source, target)
    public_values: dict[str, object] = {"updated_at": target.updated_at}
    if target.nickname != before_public[0]:
        public_values["nickname"] = target.nickname
    if target.avatar_url != before_public[1]:
        public_values["avatar_url"] = target.avatar_url
    updated_target = repository.update_fields(
        User,
        values=public_values,
        filters=(
            RdbFilter("id", "eq", target.id),
            RdbFilter("account_kind", "eq", "wechat"),
            RdbFilter("account_status", "eq", "active"),
        ),
    )
    if updated_target is None:
        raise MergeConsistency("正式账户公开资料条件更新未收敛")


def _complete_cloudbase_merge(
    repository: CloudBaseRepository,
    *,
    source_id: int,
    target_id: int,
) -> None:
    completed = repository.update_fields(
        User,
        values={
            "account_status": "merged",
            "merged_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        filters=(
            RdbFilter("id", "eq", source_id),
            RdbFilter("account_kind", "eq", "guest"),
            RdbFilter("account_status", "eq", "merging"),
            RdbFilter("merged_into_user_id", "eq", target_id),
        ),
    )
    if completed is not None:
        return
    reread = repository.get(User, source_id)
    if (
        reread is None
        or reread.account_status != "merged"
        or reread.merged_into_user_id != target_id
    ):
        raise MergeConsistency("游客合并完成状态未收敛", status_code=500)


def _merge_cloudbase(
    repository: CloudBaseRepository,
    source: User,
    target: User,
) -> MergeSummary:
    current_source, current_target = _prepare_cloudbase_merge(
        repository,
        source,
        target,
    )
    if current_source.account_status == "merged":
        return MergeSummary()
    source_id = current_source.id
    target_id = current_target.id
    if source_id is None or target_id is None:
        raise MergeConsistency("合并账户缺少主键")
    _update_cloudbase_public_profile(repository, current_source, current_target)

    recommendation_events_moved = _merge_recommendation_events_cloudbase(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    daily_logs_moved, daily_logs_merged = _merge_daily_logs_cloudbase(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    favorites_moved, favorites_deleted = _merge_favorites_cloudbase(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    dining_memories_moved, dining_memories_merged = (
        _merge_dining_memories_cloudbase(
            repository,
            source_id=source_id,
            target_id=target_id,
        )
    )
    profiles_moved, profiles_merged = _merge_profile_cloudbase(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    _assert_cloudbase_merge_consistent(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    _complete_cloudbase_merge(
        repository,
        source_id=source_id,
        target_id=target_id,
    )
    return MergeSummary(
        favorites_moved=favorites_moved,
        favorites_deleted=favorites_deleted,
        recommendation_events_moved=recommendation_events_moved,
        daily_logs_moved=daily_logs_moved,
        daily_logs_merged=daily_logs_merged,
        dining_memories_moved=dining_memories_moved,
        dining_memories_merged=dining_memories_merged,
        profiles_moved=profiles_moved,
        profiles_merged=profiles_merged,
    )


def _merge_sqlalchemy(session: Session, source: User, target: User) -> MergeSummary:
    if source.id is None or target.id is None:
        raise ValueError("source and target must be persisted")
    if source.account_kind != "guest":
        raise ValueError("merge source must be a guest")
    if target.account_kind != "wechat" or target.account_status != "active":
        raise ValueError("merge target must be an active WeChat user")
    if (
        source.merged_into_user_id is not None
        and source.merged_into_user_id != target.id
    ):
        raise MergeTargetConflict
    if source.account_status == "merged":
        return MergeSummary()

    if source.account_status == "active":
        source.account_status = "merging"
        source.merged_into_user_id = target.id
        source.merge_started_at = datetime.utcnow()
        session.add(source)
        session.commit()
        session.refresh(source)

    try:
        _merge_public_profile(source, target)
        recommendation_events_moved = _merge_recommendation_events_sqlalchemy(
            session,
            source_id=source.id,
            target_id=target.id,
        )
        daily_logs_moved, daily_logs_merged = _merge_daily_logs_sqlalchemy(
            session,
            source_id=source.id,
            target_id=target.id,
        )
        favorites_moved, favorites_deleted = _merge_favorites_sqlalchemy(
            session,
            source_id=source.id,
            target_id=target.id,
        )
        dining_memories_moved, dining_memories_merged = (
            _merge_dining_memories_sqlalchemy(
                session,
                source_id=source.id,
                target_id=target.id,
            )
        )
        profiles_moved, profiles_merged = _merge_profile_sqlalchemy(
            session,
            source_id=source.id,
            target_id=target.id,
        )
        _assert_sqlalchemy_merge_consistent(
            session,
            source_id=source.id,
            target_id=target.id,
        )
        source.account_status = "merged"
        source.merged_at = datetime.utcnow()
        session.add(target)
        session.add(source)
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(source)
    session.refresh(target)
    return MergeSummary(
        favorites_moved=favorites_moved,
        favorites_deleted=favorites_deleted,
        recommendation_events_moved=recommendation_events_moved,
        daily_logs_moved=daily_logs_moved,
        daily_logs_merged=daily_logs_merged,
        dining_memories_moved=dining_memories_moved,
        dining_memories_merged=dining_memories_merged,
        profiles_moved=profiles_moved,
        profiles_merged=profiles_merged,
    )


def merge_guest_into_wechat(
    session: DatabaseSession,
    source: User,
    target: User,
) -> MergeSummary:
    """Merge one guest account into one active WeChat account."""
    if is_cloudbase_repository(session):
        return _merge_cloudbase(session, source, target)
    return _merge_sqlalchemy(session, source, target)
