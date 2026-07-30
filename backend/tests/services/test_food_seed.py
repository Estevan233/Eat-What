"""T07 食物库 seed 导入 service 单测。

覆盖：
1. import_seed 从默认 JSON 导入 → 条数对、字段对
2. 重复 import_seed 幂等（清表重灌，条数不变）
3. food_service.get_all 分页 + category 过滤
4. food_service.get_by_id / get_by_name
5. food_service.search 模糊搜索
6. import_seed 文件不存在 → FileNotFoundError
"""
import json

import pytest

from app.services import food_service
from app.services.food_seed import DEFAULT_SEED_PATH, import_seed


def test_import_seed_from_default_json(session):
    """从默认 backend/data/food_seed.json 导入。"""
    count = import_seed(session, DEFAULT_SEED_PATH)
    assert count == food_service.count(session)
    assert count >= 30  # 第1步至少 30 道，第2步会扩到 200


def test_import_seed_is_idempotent(session):
    """重复导入幂等：第二次条数与第一次相同（清表重灌）。"""
    c1 = import_seed(session, DEFAULT_SEED_PATH)
    c2 = import_seed(session, DEFAULT_SEED_PATH)
    assert c1 == c2
    assert food_service.count(session) == c2


def test_import_seed_fields_populated(session):
    """导入后字段正确填充（拿第一条验证）。"""
    import_seed(session, DEFAULT_SEED_PATH)
    items, _ = food_service.get_all(session, page=1, size=1)
    assert len(items) == 1
    f = items[0]
    assert f.name
    assert f.category
    assert f.nature in {"cold", "cool", "neutral", "warm", "hot"}
    assert f.cooking_method
    assert isinstance(f.ingredients_json, list)
    assert isinstance(f.suitable_constitutions_json, list)
    # to_read_dict 去掉 _json 后缀
    d = f.to_read_dict()
    assert "ingredients" in d
    assert "ingredients_json" not in d
    assert "nutrition" in d
    assert "nutrition_json" not in d


def test_get_all_pagination(session):
    """分页：page=1 size=5 返回 5 条，page=2 size=5 返回下一批。"""
    import_seed(session, DEFAULT_SEED_PATH)
    items1, total = food_service.get_all(session, page=1, size=5)
    items2, _ = food_service.get_all(session, page=2, size=5)
    assert len(items1) == 5
    assert len(items2) == 5
    assert total >= 30
    # 两页不重叠
    ids1 = {f.id for f in items1}
    ids2 = {f.id for f in items2}
    assert ids1.isdisjoint(ids2)


def test_get_all_category_filter(session):
    """category 过滤只返回对应类别。"""
    import_seed(session, DEFAULT_SEED_PATH)
    items, total = food_service.get_all(session, page=1, size=50, category="soup")
    assert total == len(items)
    assert total > 0
    assert all(f.category == "soup" for f in items)


def test_get_by_id(session):
    """按 id 取单条。"""
    import_seed(session, DEFAULT_SEED_PATH)
    items, _ = food_service.get_all(session, page=1, size=1)
    fid = items[0].id
    assert fid is not None
    f = food_service.get_by_id(session, fid)
    assert f is not None
    assert f.id == fid


def test_get_by_id_returns_none_for_missing(session):
    """不存在的 id 返回 None。"""
    assert food_service.get_by_id(session, 99999) is None


def test_get_by_name(session):
    """按精确 name 取单条。"""
    import_seed(session, DEFAULT_SEED_PATH)
    f = food_service.get_by_name(session, "番茄炒蛋")
    assert f is not None
    assert f.name == "番茄炒蛋"


def test_search_fuzzy(session):
    """模糊搜索：搜「番茄」返回所有含番茄的菜。"""
    import_seed(session, DEFAULT_SEED_PATH)
    results = food_service.search(session, "番茄")
    assert len(results) >= 2  # 番茄炒蛋 + 番茄炖牛腩
    assert all("番茄" in f.name for f in results)


def test_search_empty_query_returns_empty(session):
    """空查询返回空列表。"""
    import_seed(session, DEFAULT_SEED_PATH)
    assert food_service.search(session, "") == []
    assert food_service.search(session, "   ") == []


def test_import_seed_file_not_found(session, tmp_path):
    """文件不存在 → FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        import_seed(session, tmp_path / "nope.json")


def test_import_seed_custom_json(session, tmp_path):
    """自定义 JSON 文件导入。"""
    custom = [
        {
            "name": "测试菜", "category": "test",
            "ingredients": ["a", "b"],
            "calories_kcal_per_100g": 50,
            "nutrition": {"protein_g": 1, "fat_g": 2, "carb_g": 3, "fiber_g": 4},
            "nature": "neutral", "flavor": ["sweet"],
            "suitable_constitutions": ["pinghe"],
            "suitable_weathers": ["any"],
            "tags": ["test"],
            "cooking_method": "other", "cooking_time_min": 10,
            "description": "测试用",
        }
    ]
    p = tmp_path / "custom.json"
    p.write_text(json.dumps(custom), encoding="utf-8")
    count = import_seed(session, p)
    assert count == 1
    f = food_service.get_by_name(session, "测试菜")
    assert f is not None
    assert f.calories_kcal_per_100g == 50
    assert f.nutrition_json["protein_g"] == 1
