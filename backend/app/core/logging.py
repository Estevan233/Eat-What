"""日志配置 - structlog 结构化日志。

学习点：
- structlog 输出 JSON 字符串，方便日后用 ELK / Loki 检索
- 开发期用 ConsoleRenderer 美化，生产用 JSONRenderer
- RequestContextMiddleware 给每个请求分配 request_id，串联日志
"""
import logging
import uuid
from collections.abc import Awaitable, Callable
from time import perf_counter

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def configure_logging(debug: bool = False) -> None:
    """启动时调用一次。"""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")

    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if debug
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """给每个请求分配 request_id，写进响应头。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        started = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        app_timing = f"app;dur={duration_ms:.1f}"
        existing_timing = response.headers.get("Server-Timing")
        response.headers["Server-Timing"] = (
            f"{existing_timing}, {app_timing}" if existing_timing else app_timing
        )
        structlog.get_logger().info(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return response
