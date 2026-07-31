"""收藏 service - 增删查收藏。

学习点：
- toggle_favorite 用 INSERT OR IGNORE 语义：已收藏时取消，未收藏时新增
- list_favorites JOIN Food 返回完整菜信息（前端收藏页直接展示）
- is_favorited 批量判断，FoodCard 渲染时用
"""
from sqlmodel import Session, select

from app.models.favorite import Favorite
from app.models.food import Food


def toggle_favorite(session: Session, user_id: int, food_id: int) -> bool:
    """切换收藏状态。返回 True=已收藏，False=已取消。"""
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


def is_favorited(session: Session, user_id: int, food_id: int) -> bool:
    """单道菜是否已收藏。"""
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .where(Favorite.food_id == food_id)
    )
    return session.exec(stmt).first() is not None


def list_favorited_ids(session: Session, user_id: int) -> list[int]:
    """取用户所有收藏的 food_id 列表。FoodCard 批量渲染时用。"""
    stmt = (
        select(Favorite.food_id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def list_favorites(
    session: Session,
    user_id: int,
    *,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Food], int]:
    """分页查询收藏，JOIN Food 返回完整菜信息。

    Returns:
        (foods, total) — foods 是 Food 列表，total 是总收藏数
    """
    stmt = (
        select(Food)
        .join(Favorite, Favorite.food_id == Food.id)  # type: ignore[arg-type]
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())  # type: ignore[attr-defined]
    )
    total = session.exec(
        select(Favorite).where(Favorite.user_id == user_id)
    ).all()
    total_count = len(total)

    offset = (page - 1) * size
    items = list(session.exec(stmt.offset(offset).limit(size)).all())
    return items, total_count
