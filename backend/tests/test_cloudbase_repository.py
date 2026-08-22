"""High-level CloudBase repository model mapping and isolation contracts."""

import json
from datetime import datetime

from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.cloudbase_rdb import RdbFilter, RdbResult
from app.repositories.cloudbase_repository import CloudBaseRepository


class StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []

    def select(self, table: str, **kwargs):
        self.calls.append(("select", table, kwargs))
        return RdbResult(
            rows=[
                {
                    "user_id": 7,
                    "birthday": "2000-01-01",
                    "gender": "male",
                    "height_cm": 180,
                    "weight_kg": 70.5,
                    "forbidden_tags": json.dumps(["pork", "shellfish"]),
                    "constitution_type": None,
                    "constitution_scores": None,
                    "updated_at": "2026-08-20T12:00:00",
                }
            ],
            status_code=200,
            total=1,
        )

    def upsert(self, table: str, values):
        self.calls.append(("upsert", table, values))
        return RdbResult(rows=[values], status_code=201, affected=1)


def test_select_model_decodes_json_and_preserves_owned_filter() -> None:
    client = StubClient()
    repository = CloudBaseRepository(client)

    profile = repository.first(
        UserProfile,
        filters=(RdbFilter("user_id", "eq", 7),),
    )

    assert profile is not None
    assert profile.forbidden_tags == ["pork", "shellfish"]
    assert profile.updated_at == datetime(2026, 8, 20, 12, 0)
    method, table, kwargs = client.calls[0]
    assert method == "select"
    assert table == "user_profiles"
    assert kwargs["filters"] == (RdbFilter("user_id", "eq", 7),)
    assert kwargs["limit"] == 1


def test_select_model_restores_non_nullable_json_collection_default() -> None:
    """CloudBase may represent an empty JSON array as null on a later GET."""
    client = StubClient()
    client.select = lambda table, **kwargs: RdbResult(
        rows=[
            {
                "user_id": 7,
                "birthday": "2000-01-01",
                "gender": "male",
                "height_cm": 180,
                "weight_kg": 70.5,
                "forbidden_tags": None,
                "constitution_type": None,
                "constitution_scores": None,
                "updated_at": "2026-08-20T12:00:00",
            }
        ],
        status_code=200,
        total=1,
    )
    repository = CloudBaseRepository(client)

    profile = repository.first(UserProfile)

    assert profile is not None
    assert profile.forbidden_tags == []


def test_upsert_model_serializes_json_and_datetime() -> None:
    client = StubClient()
    repository = CloudBaseRepository(client)
    profile = UserProfile(
        user_id=7,
        birthday="2000-01-01",
        gender="male",
        height_cm=180,
        weight_kg=70.5,
        forbidden_tags=["pork"],
        updated_at=datetime(2026, 8, 20, 12, 0),
    )

    saved = repository.upsert(profile)

    assert saved.user_id == 7
    _, table, values = client.calls[-1]
    assert table == "user_profiles"
    assert json.loads(values["forbidden_tags"]) == ["pork"]
    assert values["constitution_scores"] is None
    assert values["updated_at"] == "2026-08-20T12:00:00"


def test_update_omits_primary_key_from_patch_body() -> None:
    client = StubClient()

    def update(table, values, *, filters):
        client.calls.append(
            ("update", table, {"values": values, "filters": filters}),
        )
        return RdbResult(
            rows=[{"id": 9, **values}],
            status_code=200,
            affected=1,
        )

    client.update = update
    repository = CloudBaseRepository(client)
    user = User(id=9, openid="openid-9", nickname="更新后")

    saved = repository.update(
        user,
        filters=(RdbFilter("id", "eq", 9),),
    )

    assert saved.id == 9
    _, _, payload = client.calls[-1]
    assert "id" not in payload["values"]
