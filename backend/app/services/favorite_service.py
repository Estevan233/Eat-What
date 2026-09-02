"""收藏 service - 增删查收藏。

学习点：
- toggle_favorite 用 INSERT OR IGNORE 语义：已收藏时取消，未收藏时新增
- list_favorites JOIN Food 返回完整菜信息（前端收藏页直接展示）
- is_favorited 批量判断，FoodCard 渲染时用
"""
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlmodel import select

from app.core.errors import NotFoundError, ValidationError
from app.models.favorite import Favorite
from app.models.food import Food
from app.repositories.cloudbase_rdb import RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository


def toggle_favorite(session: DatabaseSession, user_id: int, food_id: int) -> bool:
    """切换收藏状态。返回 True=已收藏，False=已取消。"""
    if is_cloudbase_repository(session):
        filters = (
            RdbFilter('user_id', 'eq', user_id),
            RdbFilter('food_id', 'eq', food_id),
        )
        existing = session.first(Favorite, filters=filters)
        if existing is not None:
            session.delete(Favorite, filters=filters)
            return False
        session.insert(Favorite(user_id=user_id, food_id=food_id))
        return True

    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .where(Favorite.food_id == food_id)
    )
    existing = session.exec(stmt).first()

    if existing is not None:
        session.delete(existing)
        session.commit()
        return False

    record = Favorite(user_id=user_id, food_id=food_id)
    session.add(record)
    session.commit()
    session.refresh(record)
    return True


def is_favorited(session: DatabaseSession, user_id: int, food_id: int) -> bool:
    """单道菜是否已收藏。"""
    if is_cloudbase_repository(session):
        return session.first(
            Favorite,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('food_id', 'eq', food_id),
            ),
        ) is not None
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .where(Favorite.food_id == food_id)
    )
    return session.exec(stmt).first() is not None


def list_favorited_ids(session: DatabaseSession, user_id: int) -> list[int]:
    """取用户所有收藏的 food_id 列表（自定义收藏 food_id 为空，跳过）。FoodCard 批量渲染时用。"""
    if is_cloudbase_repository(session):
        records = session.list(
            Favorite,
            filters=(RdbFilter('user_id', 'eq', user_id),),
            order=(RdbOrder('created_at', 'desc'),),
        )
        return [record.food_id for record in records if record.food_id is not None]
    stmt = (
        select(Favorite.food_id)
        .where(Favorite.user_id == user_id)
        .where(Favorite.food_id.is_not(None))  # type: ignore[union-attr]
        .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
    )
    return [int(fid) for fid in session.exec(stmt).all() if fid is not None]


def list_recent_favorites(
    session: DatabaseSession,
    user_id: int,
    *,
    days: int = 30,
    as_of: date | None = None,
) -> list[Favorite]:
    """取包含 as_of 当天在内的近 N 天收藏行（闭区间），用于 rules_v6 偏好画像。

    返回 Favorite 行（含 created_at）而非只有 id，使收藏可按时间衰减。
    SQLite/SQLModel 与 CloudBase Repository 使用相同的闭区间语义：
    [as_of - (days-1), as_of]，两端包含。
    """
    end = as_of or date.today()
    start = end - timedelta(days=days - 1)
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)  # 闭区间上界用次日 0 点
    if is_cloudbase_repository(session):
        return session.list(
            Favorite,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('created_at', 'gte', start_dt),
                RdbFilter('created_at', 'lt', end_dt),
            ),
            order=(RdbOrder('created_at', 'desc'),),
        )
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .where(Favorite.created_at >= start_dt)
        .where(Favorite.created_at < end_dt)
        .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def list_favorites(
    session: DatabaseSession,
    user_id: int,
    *,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Food], int]:
    """分页查询收藏，JOIN Food 返回完整菜信息。

    Returns:
        (foods, total) — foods 是 Food 列表，total 是总收藏数
    """
    if is_cloudbase_repository(session):
        records, total = session.list_with_total(
            Favorite,
            filters=(RdbFilter('user_id', 'eq', user_id),),
            order=(RdbOrder('created_at', 'desc'),),
            limit=size,
            offset=(page - 1) * size,
        )
        food_ids = [record.food_id for record in records]
        if not food_ids:
            return [], total
        foods = session.list(
            Food,
            filters=(RdbFilter('id', 'in', food_ids),),
        )
        by_id = {food.id: food for food in foods}
        return [by_id[food_id] for food_id in food_ids if food_id in by_id], total

    stmt = (
        select(Food)
        .join(Favorite, Favorite.food_id == Food.id)  # type: ignore[arg-type]
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
    )
    favorite_rows = session.exec(
        select(Favorite).where(Favorite.user_id == user_id)
    ).all()
    total_count = len(favorite_rows)

    offset = (page - 1) * size
    items = list(session.exec(stmt.offset(offset).limit(size)).all())
    return items, total_count


def _load_foods_map(
    session: DatabaseSession,
    food_ids: list[int | None],
) -> dict[int, Food]:
    """按 id 批量取 Food；空入参直接返回空表。"""
    ids = [fid for fid in food_ids if fid is not None]
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    if is_cloudbase_repository(session):
        foods = session.list(Food, filters=(RdbFilter('id', 'in', ids),))
    else:
        foods = list(
            session.exec(
                select(Food).where(Food.id.in_(ids))  # type: ignore[union-attr]
            ).all()
        )
    return {food.id: food for food in foods if food.id is not None}


def list_favorites_detailed(
    session: DatabaseSession,
    user_id: int,
    *,
    page: int = 1,
    size: int = 20,
    query: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """收藏列表（含自定义收藏）+ 关键词搜索。

    返回条目结构：{favorite_id, food_id, custom_name, note, created_at, food}
    food 仅有关联候选菜的条目才有。搜索在 Python 侧做（个人级数据量），
    匹配范围：自定义名 / 候选菜名 / 候选菜分类 / 备注。
    """
    if is_cloudbase_repository(session):
        rows = session.list(
            Favorite,
            filters=(RdbFilter('user_id', 'eq', user_id),),
            order=(RdbOrder('created_at', 'desc'),),
        )
    else:
        rows = list(
            session.exec(
                select(Favorite)
                .where(Favorite.user_id == user_id)
                .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
            ).all()
        )

    keyword = (query or "").strip().casefold()
    foods_by_id = _load_foods_map(session, [row.food_id for row in rows if row.food_id])

    matched: list[dict[str, Any]] = []
    for row in rows:
        food = foods_by_id.get(row.food_id) if row.food_id else None
        if keyword:
            haystacks = [row.custom_name or "", row.note or ""]
            if food is not None:
                haystacks.append(food.name)
                haystacks.append(food.category)
            if not any(keyword in text.casefold() for text in haystacks):
                continue
        matched.append(
            {
                "favorite_id": row.id,
                "food_id": row.food_id,
                "custom_name": row.custom_name,
                "note": row.note,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "food": food,
            }
        )

    total = len(matched)
    offset = (page - 1) * size
    return matched[offset : offset + size], total


def add_custom_favorite(
    session: DatabaseSession,
    user_id: int,
    *,
    custom_name: str,
    note: str | None = None,
) -> Favorite:
    """新增一条自定义收藏（不依赖候选库）。同名重复返回 None。"""
    name = custom_name.strip()
    if not name:
        raise ValidationError("收藏名称不能为空")
    if is_cloudbase_repository(session):
        existing = session.first(
            Favorite,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('custom_name', 'eq', name),
            ),
        )
    else:
        existing = session.exec(
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .where(Favorite.custom_name == name)
        ).first()
    if existing is not None:
        raise ValidationError("已经收藏过这道菜了")
    record = Favorite(
        user_id=user_id,
        food_id=None,
        custom_name=name,
        note=(note.strip() or None) if note else None,
    )
    if is_cloudbase_repository(session):
        return session.insert(record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_favorite_by_id(
    session: DatabaseSession,
    user_id: int,
    favorite_id: int,
) -> Favorite | None:
    """按 id 取当前用户的一条收藏；不存在或不属于该用户返回 None。"""
    if is_cloudbase_repository(session):
        return session.first(
            Favorite,
            filters=(
                RdbFilter('id', 'eq', favorite_id),
                RdbFilter('user_id', 'eq', user_id),
            ),
        )
    return session.exec(
        select(Favorite)
        .where(Favorite.id == favorite_id)
        .where(Favorite.user_id == user_id)
    ).first()


def update_favorite_note(
    session: DatabaseSession,
    user_id: int,
    favorite_id: int,
    note: str | None,
) -> Favorite:
    """编辑收藏备注。"""
    record = get_favorite_by_id(session, user_id, favorite_id)
    if record is None or record.id is None:
        raise NotFoundError("favorite", favorite_id)
    record.note = (note.strip() or None) if note else None
    if is_cloudbase_repository(session):
        return session.update(
            record,
            filters=(
                RdbFilter('id', 'eq', record.id),
                RdbFilter('user_id', 'eq', user_id),
            ),
        )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def delete_favorite(session: DatabaseSession, user_id: int, favorite_id: int) -> None:
    """删除当前用户的一条收藏（普通/自定义通用）。"""
    if is_cloudbase_repository(session):
        filters = (
            RdbFilter('id', 'eq', favorite_id),
            RdbFilter('user_id', 'eq', user_id),
        )
        if session.first(Favorite, filters=filters) is None:
            raise NotFoundError("favorite", favorite_id)
        session.delete(Favorite, filters=filters)
        return
    record = get_favorite_by_id(session, user_id, favorite_id)
    if record is None:
        raise NotFoundError("favorite", favorite_id)
    session.delete(record)
    session.commit()
