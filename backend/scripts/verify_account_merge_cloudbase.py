"""Destructive-but-self-cleaning CloudBase REST account-merge contract check.

Run only inside a deployed CloudRun container after Alembic migration 07.
The script creates randomized diagnostic rows, exercises the real HTTPS
repository, verifies the merge, and removes every diagnostic row in ``finally``.
It never prints API keys, OpenIDs, JWTs, or profile contents.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from app.core.config import get_settings
from app.core.deps import resolve_token_user
from app.core.errors import AuthError
from app.core.security import create_access_token
from app.models.daily_log import DailyLog
from app.models.dining_memory import DiningMemory
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.cloudbase_rdb import CloudBaseRdbClient, RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import CloudBaseRepository
from app.services.account_merge_service import merge_guest_into_wechat


def _build_repository() -> CloudBaseRepository:
    settings = get_settings()
    api_key = settings.cloudbase_server_api_key
    if api_key is None or not api_key.get_secret_value():
        raise SystemExit("CLOUDBASE_APIKEY is not injected")
    return CloudBaseRepository(
        CloudBaseRdbClient(
            env_id=settings.cloudbase_env_id,
            api_key=api_key,
            timeout_seconds=settings.cloudbase_db_timeout_seconds,
            read_retries=settings.cloudbase_db_read_retries,
        )
    )


def _first_food_id(repository: CloudBaseRepository) -> int:
    food = repository.first(Food, order=(RdbOrder("id", "asc"),))
    if food is None or food.id is None:
        raise RuntimeError("foods seed is missing")
    return food.id


def _delete_user_rows(repository: CloudBaseRepository, user_id: int) -> None:
    owner_filter = (RdbFilter("user_id", "eq", user_id),)
    # Daily logs reference recommendation events, so projections go first.
    repository.delete(DailyLog, filters=owner_filter)
    repository.delete(Favorite, filters=owner_filter)
    repository.delete(DiningMemory, filters=owner_filter)
    repository.delete(UserProfile, filters=owner_filter)
    repository.delete(RecommendationEvent, filters=owner_filter)


def _cleanup(repository: CloudBaseRepository, openids: tuple[str, str]) -> None:
    users: list[User] = []
    for openid in openids:
        user = repository.first(User, filters=(RdbFilter("openid", "eq", openid),))
        if user is not None and user.id is not None:
            users.append(user)
    for user in users:
        if user.id is not None:
            _delete_user_rows(repository, user.id)
    for user in users:
        if user.id is not None:
            repository.delete(User, filters=(RdbFilter("id", "eq", user.id),))


def _seed_contract_rows(
    repository: CloudBaseRepository,
    *,
    guest_openid: str,
    wechat_openid: str,
) -> tuple[User, User]:
    now = datetime.utcnow()
    guest = repository.insert(
        User(
            openid=guest_openid,
            account_kind="guest",
            account_status="active",
            nickname="真实网关游客",
            created_at=now,
            updated_at=now,
        )
    )
    target = repository.insert(
        User(
            openid=wechat_openid,
            account_kind="wechat",
            account_status="active",
            nickname="微信用户",
            created_at=now,
            updated_at=now,
        )
    )
    if guest.id is None or target.id is None:
        raise RuntimeError("diagnostic users did not return ids")

    food_id = _first_food_id(repository)
    repository.insert(Favorite(user_id=guest.id, food_id=food_id, created_at=now))
    event = repository.insert(
        RecommendationEvent(
            request_id=f"diagnostic-{uuid4().hex}",
            user_id=guest.id,
            event_date=date.today(),
            recommended_food_ids_json=[food_id],
            primary_food_ids_json=[food_id],
            engine="contract-test",
            scorer_version="contract-test",
            builder_version="contract-test",
            created_at=now,
        )
    )
    if event.id is None:
        raise RuntimeError("diagnostic event did not return id")
    repository.insert(
        DailyLog(
            user_id=guest.id,
            log_date=date.today(),
            recommendation_event_id=event.id,
            recommended_food_ids_json=[food_id],
            chosen_food_ids_json=[food_id],
            created_at=now,
            updated_at=now,
        )
    )
    repository.insert(
        DiningMemory(
            user_id=guest.id,
            shop_name="真实网关诊断店",
            dish_name="真实网关诊断菜",
            normalized_shop_name="真实网关诊断店",
            normalized_dish_name="真实网关诊断菜",
            verdict="liked",
            note="contract-test",
            created_at=now,
            updated_at=now,
        )
    )
    repository.insert(
        UserProfile(
            user_id=guest.id,
            birthday="2000-01-01",
            gender="other",
            forbidden_tags=[],
            updated_at=now,
        )
    )
    return guest, target


def _assert_merged_contract(
    repository: CloudBaseRepository,
    *,
    guest_id: int,
    target_id: int,
    recommendation_events_moved: int,
) -> None:
    source = repository.get(User, guest_id)
    formal = repository.get(User, target_id)
    if source is None or source.account_status != "merged":
        raise RuntimeError("guest tombstone did not reach merged")
    if source.merged_into_user_id != target_id:
        raise RuntimeError("guest tombstone target mismatch")
    if formal is None or formal.nickname != "真实网关游客":
        raise RuntimeError("formal public-profile fill contract failed")
    if recommendation_events_moved != 1:
        raise RuntimeError("recommendation-event merge count mismatch")


def _assert_source_rows_cleared(
    repository: CloudBaseRepository,
    *,
    guest_id: int,
) -> None:
    for model in (Favorite, RecommendationEvent, DailyLog, DiningMemory):
        if repository.first(
            model,
            filters=(RdbFilter("user_id", "eq", guest_id),),
        ) is not None:
            raise RuntimeError(f"source rows remain in {model.__tablename__}")
    if repository.get(UserProfile, guest_id) is not None:
        raise RuntimeError("source profile remains")


def _assert_merged_token_rejected(
    repository: CloudBaseRepository,
    *,
    guest_id: int,
) -> None:
    token = create_access_token(guest_id)
    try:
        resolve_token_user(repository, token, require_active=True)
    except AuthError:
        return
    raise RuntimeError("merged guest token remained active")


def verify_real_account_merge(repository: CloudBaseRepository) -> None:
    suffix = uuid4().hex
    guest_openid = f"diagnostic:guest:{suffix}"
    wechat_openid = f"diagnostic:wechat:{suffix}"
    try:
        guest, target = _seed_contract_rows(
            repository,
            guest_openid=guest_openid,
            wechat_openid=wechat_openid,
        )
        if guest.id is None or target.id is None:
            raise RuntimeError("diagnostic users are not persisted")

        zero_row = repository.update_fields(
            User,
            values={"nickname": "must-not-apply"},
            filters=(
                RdbFilter("id", "eq", guest.id),
                RdbFilter("account_status", "eq", "merged"),
            ),
        )
        if zero_row is not None:
            raise RuntimeError("conditional PATCH zero-row contract failed")

        summary = merge_guest_into_wechat(repository, guest, target)
        merge_guest_into_wechat(repository, guest, target)

        _assert_merged_contract(
            repository,
            guest_id=guest.id,
            target_id=target.id,
            recommendation_events_moved=summary.recommendation_events_moved,
        )
        _assert_source_rows_cleared(repository, guest_id=guest.id)
        _assert_merged_token_rejected(repository, guest_id=guest.id)
    finally:
        _cleanup(repository, (guest_openid, wechat_openid))


def main() -> None:
    repository = _build_repository()
    try:
        verify_real_account_merge(repository)
    finally:
        repository.close()
    print("cloudbase_account_merge_contract_ok")


if __name__ == "__main__":
    main()
