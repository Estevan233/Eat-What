"""食物查询 service - 推荐算法与 API 路由调它。

学习点：
- service 层 = 业务规则，路由层只负责「收请求、调 service、返响应」
- 分页用 offset/limit，MVP 200 条够用；未来上万条再换 cursor
- search 用 SQL LIKE，%q% 模糊匹配；中文 LIKE 走全表扫描但数据量小可接受
"""
from typing import cast

from sqlmodel import col, select

from app.models.food import Food
from app.models.recipe import Recipe
from app.repositories.cloudbase_rdb import RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository

REST_CATALOG_CACHE_SECONDS = 10 * 60


def get_recommendation_catalog(
    session: DatabaseSession,
) -> tuple[list[Food], dict[int, Recipe]]:
    """一次查询取齐可推荐食物及其菜谱，避免分页统计和全表菜谱查询。"""
    if is_cloudbase_repository(session):
        cached = cast(
            tuple[list[Food], dict[int, Recipe]] | None,
            session.cache_get(
                'recommendation_catalog',
                max_age_seconds=REST_CATALOG_CACHE_SECONDS,
            ),
        )
        if cached is not None:
            return cached
        rest_foods = session.list(
            Food,
            filters=(RdbFilter('recipe_ready', 'eq', True),),
            order=(RdbOrder('id'),),
        )
        food_ids = [food.id for food in rest_foods if food.id is not None]
        if not food_ids:
            return [], {}
        rest_recipes = session.list(
            Recipe,
            filters=(RdbFilter('food_id', 'in', food_ids),),
        )
        catalog = (
            rest_foods,
            {recipe.food_id: recipe for recipe in rest_recipes},
        )
        session.cache_set('recommendation_catalog', catalog)
        return catalog

    rows = session.exec(
        select(Food, Recipe)
        .join(Recipe, col(Recipe.food_id) == col(Food.id))
        .where(col(Food.recipe_ready).is_(True))
        .order_by(col(Food.id))
    ).all()
    foods: list[Food] = []
    recipes_by_food_id: dict[int, Recipe] = {}
    for food, recipe in rows:
        if food.id is None:
            continue
        foods.append(food)
        recipes_by_food_id[food.id] = recipe
    return foods, recipes_by_food_id


def get_all(
    session: DatabaseSession,
    *,
    page: int = 1,
    size: int = 20,
    category: str | None = None,
    nature: str | None = None,
    cooking_method: str | None = None,
) -> tuple[list[Food], int]:
    """分页查询食物列表，返回 (items, total)。

    Args:
        page: 1-based 页码
        size: 每页条数（路由层会 clamp 到 1-50）
        category / nature / cooking_method: 可选过滤，None 表示不过滤

    Returns:
        (当前页 Food 列表, 总条数)
    """
    if is_cloudbase_repository(session):
        filters: list[RdbFilter] = []
        if category:
            filters.append(RdbFilter('category', 'eq', category))
        if nature:
            filters.append(RdbFilter('nature', 'eq', nature))
        if cooking_method:
            filters.append(RdbFilter('cooking_method', 'eq', cooking_method))
        return session.list_with_total(
            Food,
            filters=tuple(filters),
            order=(RdbOrder('id'),),
            limit=size,
            offset=(page - 1) * size,
        )

    stmt = select(Food)
    if category:
        stmt = stmt.where(Food.category == category)
    if nature:
        stmt = stmt.where(Food.nature == nature)
    if cooking_method:
        stmt = stmt.where(Food.cooking_method == cooking_method)

    # total 用 count(*) - 需要单独的 query，SQLModel 的 select().count() 不直接
    total = len(session.exec(stmt).all())

    offset = (page - 1) * size
    # col() 让 mypy 识别 Food.id 是列而非 int | None
    items = session.exec(stmt.offset(offset).limit(size).order_by(col(Food.id))).all()
    return list(items), total


def get_by_id(session: DatabaseSession, food_id: int) -> Food | None:
    """按 id 取单条，不存在返回 None。"""
    return session.get(Food, food_id)


def get_by_name(session: DatabaseSession, name: str) -> Food | None:
    """按精确 name 取单条（seed upsert 校验用）。"""
    if is_cloudbase_repository(session):
        return session.first(
            Food,
            filters=(RdbFilter('name', 'eq', name),),
        )
    return session.exec(select(Food).where(Food.name == name)).first()


def search(session: DatabaseSession, q: str, *, limit: int = 20) -> list[Food]:
    """按 name 模糊搜索（LIKE %q%），返回最多 limit 条。

    q 为空字符串返回空列表（路由层应拦截，但兜底）。
    """
    if not q.strip():
        return []
    if is_cloudbase_repository(session):
        return session.list(
            Food,
            filters=(RdbFilter('name', 'like', f'%{q}%'),),
            order=(RdbOrder('id'),),
            limit=limit,
        )
    pattern = f"%{q}%"
    # col().like() 让 mypy 识别列操作
    stmt = (
        select(Food).where(col(Food.name).like(pattern)).limit(limit).order_by(col(Food.id))
    )
    return list(session.exec(stmt).all())


def count(session: DatabaseSession) -> int:
    """总条数。"""
    if is_cloudbase_repository(session):
        _, total = session.list_with_total(Food, limit=1)
        return total
    return len(session.exec(select(Food)).all())
