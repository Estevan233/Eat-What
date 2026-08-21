"""应用配置 - 通过 pydantic-settings 从 .env 读取。

学习点：
- BaseSettings 会自动按字段名匹配 .env 里的同名变量
- lru_cache 让 get_settings() 单例化，避免重复读 .env
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 运行环境
    environment: str = "dev"
    debug: bool = True

    # 数据库
    database_url: str = "sqlite:///./dev.db"
    database_backend: Literal["sqlalchemy", "cloudbase_rest"] = "sqlalchemy"
    cloudbase_db_api_key: SecretStr | None = None
    cloudbase_apikey: SecretStr | None = None
    cloudbase_db_timeout_seconds: float = 5.0
    cloudbase_db_read_retries: int = 1

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 10080  # 7 天

    # 微信小程序
    wx_appid: str = ""
    wx_secret: str = ""
    cloudbase_env_id: str = ""
    enable_code2session: bool = False
    port: int = 8080

    # 和风天气（已弃用 - T09 切换到 Open-Meteo，保留字段以便回退）
    hefeng_key: str = ""
    hefeng_api: str = "https://devapi.qweather.com/v7/weather/now"
    hefeng_geo_api: str = "https://geoapi.qweather.com/v2/city/lookup"

    # Open-Meteo（T09 实际使用，免 key 免注册）
    open_meteo_api: str = "https://api.open-meteo.com/v1/forecast"

    # 高德
    amap_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def use_installed_mysql_driver(cls, value: object) -> object:
        """Accept CloudBase's standard mysql:// URI and select PyMySQL explicitly."""
        if isinstance(value, str) and value.startswith("mysql://"):
            return value.replace("mysql://", "mysql+pymysql://", 1)
        return value

    def validate_required(self) -> list[str]:
        """返回缺失或不安全的关键配置名。"""
        missing: list[str] = []
        if len(self.jwt_secret) < 32:
            missing.append("JWT_SECRET")
        if not self.wx_appid:
            missing.append("WX_APPID")
        if not self.cloudbase_env_id:
            missing.append("CLOUDBASE_ENV_ID")
        if self.enable_code2session and not self.wx_secret:
            missing.append("WX_SECRET")
        if self.environment.lower() in {"prod", "production"}:
            database_requirement = self._production_database_requirement()
            if database_requirement is not None:
                missing.append(database_requirement)
            if self.debug:
                missing.append("DEBUG")
            if self.enable_code2session:
                missing.append("ENABLE_CODE2SESSION")
            if self.jwt_algorithm != "HS256":
                missing.append("JWT_ALGORITHM")
        return missing

    @property
    def cloudbase_server_api_key(self) -> SecretStr | None:
        """Resolve the explicit app setting before CloudBase's injected standard name."""
        for candidate in (self.cloudbase_db_api_key, self.cloudbase_apikey):
            if candidate is not None and candidate.get_secret_value():
                return candidate
        return None

    def _production_database_requirement(self) -> str | None:
        if self.database_backend == "sqlalchemy":
            if not self.database_url.startswith("mysql+pymysql://"):
                return "DATABASE_URL"
            return None
        resolved_api_key = self.cloudbase_server_api_key
        api_key = resolved_api_key.get_secret_value() if resolved_api_key is not None else ""
        if not api_key:
            return "CLOUDBASE_APIKEY"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
