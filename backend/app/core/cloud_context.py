"""CloudBase 私有链路注入的可信身份上下文。"""

from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings
from app.core.errors import AppError


@dataclass(frozen=True)
class CloudIdentity:
    """完成 AppID 与环境校验后的最小微信身份。"""

    openid: str
    appid: str
    environment: str
    request_id: str | None


def read_cloud_identity(request: Request, settings: Settings) -> CloudIdentity:
    """读取并校验仅应由 CloudBase 私有链路注入的身份请求头。"""

    openid = request.headers.get("X-WX-OPENID", "").strip()
    appid = request.headers.get("X-WX-APPID", "").strip()
    environment = request.headers.get("X-WX-ENV", "").strip()

    if not openid:
        raise AppError("缺少可信微信身份", "CLOUD_IDENTITY_INVALID", 401)
    if appid != settings.wx_appid:
        raise AppError("小程序 AppID 不匹配", "CLOUD_IDENTITY_INVALID", 401)
    if environment != settings.cloudbase_env_id:
        raise AppError("CloudBase 环境不匹配", "CLOUD_IDENTITY_INVALID", 401)

    return CloudIdentity(
        openid=openid,
        appid=appid,
        environment=environment,
        request_id=request.headers.get("X-WX-REQUEST-ID"),
    )
