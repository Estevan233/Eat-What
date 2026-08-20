"""运行时配置契约测试。"""

from app.core.config import Settings


def test_cloud_mode_does_not_require_wx_secret() -> None:
    settings = Settings(
        environment="production",
        debug=False,
        database_url="mysql+pymysql://user:pass@db/eat_what",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
        wx_secret="",
    )

    assert settings.validate_required() == []


def test_cloudbase_rest_mode_requires_server_api_key_not_database_url() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_backend="cloudbase_rest",
        database_url="sqlite:///./unused.db",
        cloudbase_db_api_key="",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
    )

    missing = settings.validate_required()

    assert "CLOUDBASE_APIKEY" in missing
    assert "DATABASE_URL" not in missing


def test_cloudbase_rest_mode_stays_gated_until_runtime_repositories_are_complete() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_backend="cloudbase_rest",
        database_url="sqlite:///./unused.db",
        cloudbase_db_api_key="k" * 48,
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
    )

    assert settings.validate_required() == ["DATABASE_BACKEND_CLOUDBASE_REST_NOT_READY"]


def test_cloudbase_server_api_key_accepts_platform_injected_name(monkeypatch) -> None:
    monkeypatch.delenv("CLOUDBASE_DB_API_KEY", raising=False)
    monkeypatch.setenv("CLOUDBASE_APIKEY", "platform-injected-key")

    settings = Settings(_env_file=None)

    api_key = settings.cloudbase_server_api_key
    assert api_key is not None
    assert api_key.get_secret_value() == "platform-injected-key"


def test_cloudbase_standard_mysql_url_uses_installed_pymysql_driver() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_url="mysql://user:pass@172.17.0.15:3306/eat_what",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
    )

    assert settings.database_url == "mysql+pymysql://user:pass@172.17.0.15:3306/eat_what"
    assert settings.validate_required() == []


def test_code2session_requires_secret() -> None:
    settings = Settings(
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=True,
        wx_secret="",
    )

    assert "WX_SECRET" in settings.validate_required()


def test_short_jwt_secret_is_rejected() -> None:
    settings = Settings(
        jwt_secret="too-short",
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
    )

    assert "JWT_SECRET" in settings.validate_required()


def test_production_rejects_ephemeral_or_unsafe_runtime_settings() -> None:
    settings = Settings(
        environment="prod",
        debug=True,
        database_url="sqlite:///./dev.db",
        jwt_secret="x" * 32,
        jwt_algorithm="RS256",
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=True,
        wx_secret="legacy-secret",
    )

    assert settings.validate_required() == [
        "DATABASE_URL",
        "DEBUG",
        "ENABLE_CODE2SESSION",
        "JWT_ALGORITHM",
    ]


def test_development_keeps_sqlite_and_debug_available() -> None:
    settings = Settings(
        environment="dev",
        debug=True,
        database_url="sqlite:///./dev.db",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
    )

    assert settings.validate_required() == []
