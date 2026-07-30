"""v1 路由聚合 - main.py 只 import 一个 router，所有 v1 子路由在这里挂。"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.constitution import router as constitution_router
from app.api.v1.profile import router as profile_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(constitution_router)

__all__ = ["api_router"]
