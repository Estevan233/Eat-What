"""微信 code2session 客户端。

学习点：
- 前端 wx.login() 拿到的 code 是一次性的、5 分钟过期
- 后端必须用 AppID + Secret + code 去问微信「这个 code 是哪个 openid」
- httpx.AsyncClient 用上下文管理器，每次请求自动关连接
- errcode 0 = 成功，其他都是失败（40029 code 无效、45011 限频等）
"""
from typing import TypedDict

import httpx
import structlog

from app.core.config import get_settings
from app.core.errors import AuthError, ExternalAPIError, RateLimitError

log = structlog.get_logger()
CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class Code2SessionResult(TypedDict):
    """code2session 成功响应的结构。"""

    openid: str
    session_key: str
    unionid: str | None


class WxClient:
    """微信 code2session 调用封装。

    拆成类而不是裸函数：方便测试时 mock 整个 client，
    也方便将来加 token 刷新、access_token 缓存等。
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._timeout = 5.0

    async def code2session(self, code: str) -> Code2SessionResult:
        """拿 code 换 openid + session_key。

        Returns:
            {"openid": "...", "session_key": "...", "unionid": "..."?}
        Raises:
            AuthError: code 无效 / 已被使用 / 过期
            RateLimitError: 触发微信限频
            ExternalAPIError: 网络异常 / 非 200
        """
        params = {
            "appid": self._settings.wx_appid,
            "secret": self._settings.wx_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        log.info("wx_code2session_start", code_len=len(code))

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(CODE2SESSION_URL, params=params)
        except httpx.HTTPError as e:
            log.warning("wx_code2session_network_error", error=str(e))
            raise ExternalAPIError("wechat", f"网络异常: {e}") from None

        if resp.status_code != 200:
            log.warning("wx_code2session_http_error", status=resp.status_code)
            raise ExternalAPIError("wechat", f"HTTP {resp.status_code}") from None

        try:
            data = resp.json()
        except ValueError as e:
            raise ExternalAPIError("wechat", f"非 JSON 响应: {e}") from None

        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "unknown")
            log.warning(
                "wx_code2session_errcode",
                errcode=errcode,
                errmsg=errmsg,
            )
            # 45011 = API 频率超限；其他 errcode 通常是 code 失效
            if errcode == 45011:
                raise RateLimitError("wechat")
            raise AuthError(f"微信登录失败: [{errcode}] {errmsg}")

        # 成功响应里必须含 openid 与 session_key
        openid = data.get("openid")
        session_key = data.get("session_key")
        if not isinstance(openid, str) or not isinstance(session_key, str):
            raise ExternalAPIError("wechat", f"响应缺字段: {data}")

        unionid = data.get("unionid")
        if unionid is not None and not isinstance(unionid, str):
            unionid = None

        log.info("wx_code2session_ok", openid_len=len(openid))
        result: Code2SessionResult = {
            "openid": openid,
            "session_key": session_key,
            "unionid": unionid,
        }
        return result


# 单例 - 模块级常量，路由里直接 import 用
# 测试时 monkeypatch 这个属性即可 mock
wx_client = WxClient()
