"""Runtime service smoke tests against an in-memory CloudBase REST double."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any, ClassVar

from app.models.food import Food
from app.models.recipe import Recipe
from app.repositories.cloudbase_rdb import RdbFilter, RdbResult
from app.repositories.cloudbase_repository import CloudBaseRepository
from app.schemas.constitution import ConstitutionResult
from app.schemas.dining import DiningMemoryUpsert
from app.schemas.profile import ProfileUpsert
from app.services import (
    constitution,
    daily_service,
    dining_memory_service,
    favorite_service,
    food_service,
    profile_service,
    recipe_service,
    user_service,
)


class MemoryRdbClient:
    unique_keys: ClassVar[dict[str, tuple[str, ...]]] = {
        "users": ("openid",),
        "user_profiles": ("user_id",),
        "foods": ("name",),
        "recipes": ("food_id",),
        "favorites": ("user_id", "food_id"),
        "dining_memories": (
            "user_id",
            "normalized_shop_name",
            "normalized_dish_name",
        ),
        "recommendation_events": ("request_id",),
        "daily_logs": ("user_id", "log_date"),
    }

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.ids: dict[str, int] = {}
        self.select_calls = 0
        self.select_requests: list[tuple[str, tuple[RdbFilter, ...]]] = []
        self.write_calls: list[tuple[str, str, Any]] = []

    def close(self) -> None:
        return None

    def select(
        self,
        table: str,
        *,
        columns=("*",),
        filters=(),
        order=(),
        limit=None,
        offset=None,
        count=False,
    ) -> RdbResult:
        self.select_calls += 1
        self.select_requests.append((table, tuple(filters)))
        rows = [deepcopy(row) for row in self.tables.get(table, [])]
        rows = [row for row in rows if all(self._matches(row, item) for item in filters)]
        total = len(rows)
        for item in reversed(order):
            rows.sort(
                key=lambda row: row.get(item.field) or "",
                reverse=item.direction == "desc",
            )
        start = offset or 0
        rows = rows[start:]
        if limit is not None:
            rows = rows[:limit]
        if columns != ("*",):
            rows = [{key: row.get(key) for key in columns} for row in rows]
        return RdbResult(
            rows=rows,
            status_code=200,
            total=total if count else None,
        )

    def insert(self, table: str, values) -> RdbResult:
        self.write_calls.append(("insert", table, deepcopy(values)))
        row = deepcopy(values)
        if "id" not in row and table not in {"user_profiles"}:
            self.ids[table] = self.ids.get(table, 0) + 1
            row["id"] = self.ids[table]
        self.tables.setdefault(table, []).append(row)
        return RdbResult(rows=[deepcopy(row)], status_code=201, affected=1)

    def upsert(self, table: str, values) -> RdbResult:
        self.write_calls.append(("upsert", table, deepcopy(values)))
        row = deepcopy(values)
        keys = self.unique_keys.get(table, ("id",))
        existing = next(
            (
                item
                for item in self.tables.get(table, [])
                if all(item.get(key) == row.get(key) for key in keys)
            ),
            None,
        )
        if existing is None:
            return self.insert(table, row)
        existing.update(row)
        return RdbResult(rows=[deepcopy(existing)], status_code=200, affected=1)

    def update(self, table: str, values, *, filters) -> RdbResult:
        self.write_calls.append(
            ("update", table, {"values": deepcopy(values), "filters": filters}),
        )
        changed = []
        for row in self.tables.get(table, []):
            if all(self._matches(row, item) for item in filters):
                row.update(deepcopy(values))
                changed.append(deepcopy(row))
        return RdbResult(rows=changed, status_code=200, affected=len(changed))

    def delete(self, table: str, *, filters) -> RdbResult:
        rows = self.tables.get(table, [])
        removed = [row for row in rows if all(self._matches(row, item) for item in filters)]
        self.tables[table] = [row for row in rows if row not in removed]
        return RdbResult(
            rows=deepcopy(removed),
            status_code=200,
            affected=len(removed),
        )

    @staticmethod
    def _scalar(value):
        if isinstance(value, date | datetime):
            return value.isoformat()
        return value

    @classmethod
    def _matches(cls, row: dict[str, Any], item: RdbFilter) -> bool:
        left = cls._scalar(row.get(item.field))
        if item.operator == "in":
            return left in [cls._scalar(value) for value in item.value]
        right = cls._scalar(item.value)
        if item.operator == "eq":
            return left == right
        if item.operator == "neq":
            return left != right
        if item.operator == "gte":
            return left >= right
        if item.operator == "lte":
            return left <= right
        if item.operator == "gt":
            return left > right
        if item.operator == "lt":
            return left < right
        if item.operator == "like":
            return str(right).strip("%") in str(left)
        if item.operator == "is":
            return left is right
        raise AssertionError(f"unsupported filter {item.operator}")


def test_user_creation_uses_insert_and_existing_login_uses_filtered_update() -> None:
    client = MemoryRdbClient()
    repository = CloudBaseRepository(client)

    created = user_service.get_or_create_guest(
        repository,
        guest_id="write-contract",
        nickname="首次登录",
    )
    updated = user_service.get_or_create_guest(
        repository,
        guest_id="write-contract",
        nickname="再次登录",
    )

    assert created.id == updated.id == 1
    assert updated.nickname == "再次登录"
    user_writes = [call for call in client.write_calls if call[1] == "users"]
    assert [call[0] for call in user_writes] == ["insert", "update"]
    update_payload = user_writes[1][2]
    assert update_payload["filters"] == (RdbFilter("id", "eq", 1),)
    assert "id" not in update_payload["values"]


def test_core_services_run_without_sqlalchemy_session() -> None:
    repository = CloudBaseRepository(MemoryRdbClient())
    user = user_service.get_or_create_guest(repository, guest_id="rest-smoke")
    assert user.id == 1

    profile = profile_service.upsert_profile(
        repository,
        user.id,
        ProfileUpsert(
            birthday="2000-01-01",
            gender="male",
            height_cm=180,
            weight_kg=70,
            forbidden_tags=["pork"],
        ),
    )
    assert profile.forbidden_tags == ["pork"]

    updated_profile = profile_service.upsert_profile(
        repository,
        user.id,
        ProfileUpsert(
            birthday="2000-01-01",
            gender="male",
            height_cm=181,
            weight_kg=69,
            forbidden_tags=["pork"],
        ),
    )
    assert updated_profile.height_cm == 181
    profile_writes = [
        call for call in repository.client.write_calls
        if call[1] == "user_profiles"
    ]
    assert [call[0] for call in profile_writes] == ["insert", "update"]
    assert profile_writes[1][2]["filters"] == (
        RdbFilter("user_id", "eq", user.id),
    )

    constitution.save_constitution(
        repository,
        user.id,
        ConstitutionResult(
            primary="pinghe",
            secondary=[],
            scores_normalized={
                "pinghe": 80,
                "qixu": 20,
                "yangxu": 20,
                "yinxu": 20,
                "tanshi": 20,
                "shire": 20,
                "xueyu": 20,
                "qiyu": 20,
                "tebing": 20,
            },
            constitution_type_str="pinghe",
        ),
    )

    food = repository.insert(
        Food(
            name="番茄鸡蛋",
            category="stir_fry",
            nature="neutral",
            cooking_method="stir_fry",
            recipe_ready=True,
            meal_role="main",
        )
    )
    repository.insert(
        Recipe(
            food_id=food.id,
            nutrition_per_serving_json={
                "energy_kcal": 360,
                "protein_g": 18,
                "fat_g": 14,
                "carb_g": 38,
            },
            nutrition_basis="每人一份估算",
        )
    )
    foods, recipes = food_service.get_recommendation_catalog(repository)
    catalog_select_calls = repository.client.select_calls
    cached_foods, cached_recipes = food_service.get_recommendation_catalog(repository)
    assert [item.name for item in foods] == ["番茄鸡蛋"]
    assert recipes[food.id].food_id == food.id
    assert cached_foods is foods
    assert cached_recipes is recipes
    assert repository.client.select_calls == catalog_select_calls
    assert (
        "foods",
        (RdbFilter("recipe_ready", "is", True),),
    ) in repository.client.select_requests
    assert recipe_service.get_by_food_id(repository, food.id).food_name == "番茄鸡蛋"

    assert favorite_service.toggle_favorite(repository, user.id, food.id) is True
    favorites, total = favorite_service.list_favorites(repository, user.id)
    assert total == 1
    assert [item.id for item in favorites] == [food.id]
    assert favorite_service.toggle_favorite(repository, user.id, food.id) is False

    memory = dining_memory_service.upsert_memory(
        repository,
        user.id,
        DiningMemoryUpsert(
            shop_name="楼下小馆",
            dish_name="番茄鸡蛋",
            verdict="liked",
            note="少油",
        ),
    )
    memories, memory_total = dining_memory_service.list_memories(
        repository,
        user.id,
        page=1,
        size=20,
    )
    assert memory_total == 1
    assert memories[0].id == memory.id

    updated_memory = dining_memory_service.upsert_memory(
        repository,
        user.id,
        DiningMemoryUpsert(
            shop_name="楼下小馆",
            dish_name="番茄鸡蛋",
            verdict="avoided",
            note="偏咸",
        ),
    )
    assert updated_memory.id == memory.id
    assert updated_memory.note == "偏咸"

    first_log, first_event = daily_service.record_recommendation(
        repository,
        user.id,
        recommended_food_ids=[food.id],
        mood="neutral",
        activity_level="normal",
        weather_tag="mild",
        engine="rules_v4",
        request_id="rest-idempotent-001",
    )
    repeated_log, repeated_event = daily_service.record_recommendation(
        repository,
        user.id,
        recommended_food_ids=[999],
        mood="tired",
        activity_level="high",
        weather_tag="rainy",
        engine="rules_v4",
        request_id="rest-idempotent-001",
    )
    assert repeated_event.id == first_event.id
    assert repeated_log.id == first_log.id
    assert repeated_log.recommended_food_ids_json == [food.id]
    assert all(call[0] != "upsert" for call in repository.client.write_calls)
