"""FastAPI 入口。

学习点：
- FastAPI() 是 ASGI 应用，uvicorn 启动它
- @app.exception_handler 注册全局异常处理
- /docs 自动生成的 OpenAPI 文档
"""
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import RequestContextMiddleware, configure_logging
from app.db import init_db
from app.utils.response import error, success

log = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()

    # 启动前检查必填 env
    missing = settings.validate_required()
    if missing:
        raise RuntimeError(
            f"启动失败：.env 缺失关键字段 {missing}。请参考 .env.example 复制并填写。"
        )

    configure_logging(debug=settings.debug)
    init_db()

    app = FastAPI(
        title="今天吃啥 API",
        version="0.1.0",
        description="结合星座、节气、天气、心情、体质与忌口，给出今天该吃什么的决策建议",
    )
    app.add_middleware(RequestContextMiddleware)
    # 允许微信小程序请求（无 Origin，不严格 CORS 也能 work，但显式声明更安全）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 路由 ----
    app.include_router(api_router, prefix="/api")

    # ---- 全局异常处理器 ----
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log.warning(
            "app_error",
            path=request.url.path,
            code=exc.code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error(code=exc.code, message=exc.message),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content=error(code="INTERNAL", message="服务器内部错误"),
        )

    # ---- 健康检查 ----
    @app.get("/health", tags=["meta"])
    def health() -> dict[str, object]:
        return success(data={"status": "healthy", "env": settings.environment})

    return app


app = create_app()
