"""Stable API responses for CloudBase MySQL gateway failures."""

from dataclasses import dataclass

from app.repositories.cloudbase_rdb import CloudBaseRdbError


@dataclass(frozen=True)
class CloudBaseFailure:
    status_code: int
    code: str
    message: str


def map_cloudbase_failure(exc: CloudBaseRdbError) -> CloudBaseFailure:
    if exc.status_code in {401, 403, 404}:
        return CloudBaseFailure(
            status_code=503,
            code="SERVICE_CONFIG_ERROR",
            message="数据服务配置异常，请联系开发者",
        )
    if exc.status_code == 503:
        return CloudBaseFailure(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="数据服务正在唤醒，请稍后重试",
        )
    return CloudBaseFailure(
        status_code=502,
        code="DATABASE_ERROR",
        message="数据服务请求失败，请稍后重试",
    )
