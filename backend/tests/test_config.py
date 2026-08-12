"""运行时配置契约测试。"""

from app.core.config import Settings


def test_cloud_mode_does_not_require_wx_secret() -> None:
    settings = Settings(
        environment="production",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
        wx_secret="",
    )

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
