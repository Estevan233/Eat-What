"""应用配置 - 通过 pydantic-settings 从 .env 读取。

学习点：
- BaseSettings 会自动按字段名匹配 .env 里的同名变量
- lru_cache 让 get_settings() 单例化，避免重复读 .env
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 运行环境
    environment: str = "dev"
    debug: bool = True

    # 数据库
    database_url: str = "sqlite:///./dev.db"

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 10080  # 7 天

    # 微信小程序
    wx_appid: str = ""
    wx_secret: str = ""

    # 和风天气（已弃用 - T09 切换到 Open-Meteo，保留字段以便回退）
    hefeng_key: str = ""
    hefeng_api: str = "https://devapi.qweather.com/v7/weather/now"
    hefeng_geo_api: str = "https://geoapi.qweather.com/v2/city/lookup"

    # Open-Meteo（T09 实际使用，免 key 免注册）
    open_meteo_api: str = "https://api.open-meteo.com/v1/forecast"

    # 高德
    amap_key: str = ""

    def validate_required(self) -> list[str]:
        """返回缺失的关键字段名列表。启动时调用，缺失则 raise。"""
        missing = []
        if not self.jwt_secret:
            missing.append("JWT_SECRET")
        if not self.wx_appid:
            missing.append("WX_APPID")
        if not self.wx_secret:
            missing.append("WX_SECRET")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()
