"""Approved candidate catalog adapter tests with a CloudBase REST-shaped fake."""

from types import SimpleNamespace

from app.models.external_dining_candidate import ExternalDiningCandidate
from app.services import external_dining


class FakeCatalogRepository:
    def __init__(self, rows: list[ExternalDiningCandidate]) -> None:
        self.rows = rows

    def list(self, model, *, filters=(), order=(), limit=None, offset=None):
        assert model is ExternalDiningCandidate
        assert limit == 1000
        assert any(item.field == "review_status" for item in filters)
        assert any(item.field == "is_active" for item in filters)
        return self.rows


def _row(
    *,
    status: str = "approved",
    active: bool = True,
    meal_family: str = "noodle_meal",
    catalog_key: str = "external:test-noodle:v1",
    serving_style: str = "individual",
) -> ExternalDiningCandidate:
    return ExternalDiningCandidate(
        catalog_key=catalog_key,
        legacy_key="rule-legacy-noodle",
        dish_name="番茄鸡蛋面",
        category="汤面",
        meal_family=meal_family,
        sub_family="noodle_soup",
        serving_style=serving_style,
        source_url="https://example.org/noodle",
        source_type="restaurant_menu",
        source_checked_at="2026-08-31T10:00:00+08:00",
        review_status=status,
        is_active=active,
        energy_kcal_min_per_person=400,
        energy_kcal_max_per_person=600,
        nutrition_note="门店配方和分量未知。",
        high_protein=False,
    )


def test_catalog_adapter_preserves_legacy_key_for_replay(monkeypatch) -> None:
    repository = FakeCatalogRepository([_row()])
    monkeypatch.setattr(external_dining, "is_cloudbase_repository", lambda _: True)
    candidates = external_dining._load_catalog_rule_candidates(repository)
    assert candidates is not None
    assert len(candidates) == 1
    assert candidates[0].catalog_key == "external:test-noodle:v1"
    assert candidates[0].legacy_key == "rule-legacy-noodle"
    suggestion = external_dining._rule_suggestion(
        candidates[0],
        SimpleNamespace(audience="personal", party_size=1),
        "秋季参考",
        "未设置城市",
    )
    assert suggestion.key == "rule-legacy-noodle"


def test_catalog_flag_off_keeps_legacy_rules(monkeypatch) -> None:
    monkeypatch.setattr(
        external_dining,
        "get_settings",
        lambda: SimpleNamespace(external_catalog_enabled=False),
    )
    assert external_dining._rule_candidates_for_request(object()) == external_dining.RULE_CANDIDATES


def test_catalog_adapter_excludes_non_meal_families(monkeypatch) -> None:
    """单道菜/小吃甜点不是完整一餐，不能作为"今天吃什么"的方向。"""
    repository = FakeCatalogRepository(
        [
            _row(),
            _row(meal_family="single_dish", catalog_key="external:test-tofu:v1"),
            _row(meal_family="snack_dessert", catalog_key="external:test-pastry:v1"),
            _row(
                meal_family="single_dish",
                catalog_key="external:test-snack-side:v1",
                serving_style="shared",
            ),
        ]
    )
    monkeypatch.setattr(external_dining, "is_cloudbase_repository", lambda _: True)
    candidates = external_dining._load_catalog_rule_candidates(repository)
    assert candidates is not None
    assert [item.catalog_key for item in candidates] == ["external:test-noodle:v1"]
    assert candidates[0].meal_family == "noodle_meal"


def test_catalog_adapter_returns_none_when_all_rows_are_non_meal(monkeypatch) -> None:
    """非餐候选全部排除后回退到内置规则库，推荐仍可用。"""
    repository = FakeCatalogRepository(
        [_row(meal_family="single_dish", catalog_key="external:test-tofu:v1")]
    )
    monkeypatch.setattr(external_dining, "is_cloudbase_repository", lambda _: True)
    assert external_dining._load_catalog_rule_candidates(repository) is None

