"""食物库 seed 导入 service - 把 data/food_seed.json 灌进 foods 表。

学习点：
- 清表后导入是冷启动最省心的做法（避免增量 diff 复杂度），重复跑幂等
- name 唯一约束 + 清表后再插入，避免 upsert 时的并发/顺序问题
- service 只做数据搬运，不做 schema 校验（校验留给 validate_food_seed.py 脚本）
"""
import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.food import Food

# 默认数据文件路径 - 相对 backend/ 根目录
DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "food_seed.json"


def import_seed(session: Session, json_path: Path | str = DEFAULT_SEED_PATH) -> int:
    """清表后从 JSON 导入食物库，返回导入条数。

    Args:
        session: SQLModel Session
        json_path: food_seed.json 路径，默认指向 backend/data/food_seed.json

    Returns:
        导入的条数

    Raises:
        FileNotFoundError: json_path 不存在
        ValueError: JSON 解析失败或不是 list
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"seed 文件不存在: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"seed 文件顶层应是 list，实际是 {type(data).__name__}")

    # 清表 - 冷启动重置，幂等
    existing = session.exec(select(Food)).all()
    for r in existing:
        session.delete(r)
    session.flush()

    count = 0
    for item in data:
        record = _build_food_record(item)
        session.add(record)
        count += 1

    session.commit()
    return count


def _build_food_record(item: dict[str, Any]) -> Food:
    """把 seed JSON 的一项转成 Food ORM 对象。

    字段映射：seed 用 ingredients / nutrition / flavor 等干净 key，
    Food 表存 ingredients_json / nutrition_json 等带 _json 后缀的列。
    缺字段用默认空值，不报错（让校验脚本单独挑问题）。
    """
    return Food(
        name=item["name"],
        category=item.get("category", "other"),
        ingredients_json=list(item.get("ingredients", [])),
        calories_kcal_per_100g=item.get("calories_kcal_per_100g"),
        nutrition_json=dict(item.get("nutrition", {}) or {}),
        nature=item.get("nature", "neutral"),
        flavor_json=list(item.get("flavor", [])),
        organ_meridians_json=list(item.get("organ_meridians", [])),
        suitable_constitutions_json=list(item.get("suitable_constitutions", [])),
        suitable_weathers_json=list(item.get("suitable_weathers", ["any"])),
        forbidden_for_json=list(item.get("forbidden_for", [])),
        tags_json=list(item.get("tags", [])),
        cooking_method=item.get("cooking_method", "other"),
        cooking_time_min=item.get("cooking_time_min"),
        image_url=item.get("image_url"),
        seasonal_solar_terms_json=list(item.get("seasonal_solar_terms", [])),
        description=item.get("description"),
    )
