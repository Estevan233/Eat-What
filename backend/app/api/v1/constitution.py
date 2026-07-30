"""体质测试路由 - POST/GET /profile/constitution + GET /questions。

学习点：
- POST 在登录后写入档案，要求档案已存在（先 PUT /profile）
- GET 读上次判定结果，无记录返回 404
- GET /questions 是公开静态题库，无需登录
- response_model 用 dict[str, Any] + success() 自己包，与 auth/profile 一致
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.models.user import User
from app.schemas.constitution import ConstitutionQuestionnaire
from app.services import constitution as constitution_service
from app.services.constitution import OPTIONS, QUESTIONS
from app.utils.response import success

router = APIRouter(prefix="/profile/constitution", tags=["constitution"])


@router.get("/questions", response_model=dict[str, Any])
def get_questions_route() -> dict[str, object]:
    """返回 9 题题面 + 5 级 Likert 选项文案。

    公开端点，无需登录：题面是静态公开数据，首次进入问卷页时拉取。
    """
    return success(data={"questions": QUESTIONS, "options": OPTIONS})


@router.post("", response_model=dict[str, Any])
def submit_constitution_route(
    body: ConstitutionQuestionnaire,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """提交问卷 → 判定 → 存档 → 返回 ConstitutionResult。

    要求档案已存在（T05 PUT /profile 才能建档案）。
    若档案不存在 → 404 NotFoundError，前端引导用户先填档案。
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    result = constitution_service.judge(body.answers)
    # 档案不存在 → NotFoundError 向上抛 → 全局处理器返 404
    constitution_service.save_constitution(session, user.id, result)
    return success(data=result.model_dump())


@router.get("", response_model=dict[str, Any])
def get_constitution_route(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """读上次判定结果。不存在 → 404 NotFoundError。"""
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    result = constitution_service.get_constitution(session, user.id)
    if result is None:
        raise NotFoundError("constitution", user.id)
    return success(data=result.model_dump())
