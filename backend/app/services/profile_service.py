"""用户档案 service - 业务逻辑层。

学习点：
- upsert = update or insert：用户多次保存档案，每次都「有就更新，没有就建」
- forbidden_tags 校验放 service 层（schema 校验不了「值在动态集合内」）
- zodiac_sign 占位 None，T08 在这里加计算逻辑
"""
from datetime import datetime

from sqlmodel import Session, select

from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileRead, ProfileUpsert


def get_profile_record(session: Session, user_id: int) -> UserProfile | None:
    """读取档案模型，供推荐等服务复用，避免同一请求重复查询。"""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    return session.exec(stmt).first()


def get_profile(session: Session, user_id: int) -> ProfileRead | None:
    """读用户档案。不存在返回 None。"""
    record = get_profile_record(session, user_id)
    if record is None:
        return None
    return ProfileRead.model_validate(record.to_read_dict())


def upsert_profile(session: Session, user_id: int, data: ProfileUpsert) -> ProfileRead:
    """有就更新，没有就建。返回落库后的 ProfileRead。

    Args:
        session: SQLModel Session
        user_id: 当前用户 id（从 JWT 取）
        data: 上传的档案数据

    Returns:
        落库后的 ProfileRead（含 zodiac_sign=None 占位）
    """
    # service 层再次校验 forbidden_tags（schema 层校验不了动态集合）
    data.validate_tags()

    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    record = session.exec(stmt).first()

    if record is None:
        # 首次创建
        record = UserProfile(
            user_id=user_id,
            birthday=data.birthday,
            gender=data.gender,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            forbidden_tags=list(data.forbidden_tags),
        )
    else:
        # 已存在 → 全字段更新（forbidden_tags 整体覆盖，不做 diff）
        record.birthday = data.birthday
        record.gender = data.gender
        record.height_cm = data.height_cm
        record.weight_kg = data.weight_kg
        record.forbidden_tags = list(data.forbidden_tags)
        record.updated_at = datetime.utcnow()

    session.add(record)
    session.commit()
    session.refresh(record)
    return ProfileRead.model_validate(record.to_read_dict())
