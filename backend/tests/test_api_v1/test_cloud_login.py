"""CloudBase 私有链路登录契约测试。"""

from fastapi.testclient import TestClient


def _headers(**overrides: str) -> dict[str, str]:
    values = {
        "X-WX-OPENID": "openid-cloud-user",
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "cloud-test",
        "X-WX-REQUEST-ID": "request-123",
    }
    values.update(overrides)
    return values


def test_cloud_login_creates_and_reuses_user(client: TestClient) -> None:
    first = client.post("/api/v1/auth/cloud-login", headers=_headers())
    second = client.post("/api/v1/auth/cloud-login", headers=_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]
    assert first.json()["data"]["token"]


def test_cloud_login_rejects_missing_openid(client: TestClient) -> None:
    headers = _headers()
    headers.pop("X-WX-OPENID")

    response = client.post("/api/v1/auth/cloud-login", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == "CLOUD_IDENTITY_INVALID"


def test_cloud_login_rejects_wrong_appid(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/cloud-login",
        headers=_headers(**{"X-WX-APPID": "wx-wrong"}),
    )

    assert response.status_code == 401
    assert response.json()["code"] == "CLOUD_IDENTITY_INVALID"


def test_cloud_login_rejects_wrong_environment(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/cloud-login",
        headers=_headers(**{"X-WX-ENV": "cloud-wrong"}),
    )

    assert response.status_code == 401
    assert response.json()["code"] == "CLOUD_IDENTITY_INVALID"


def test_wx_login_is_disabled_without_compatibility_flag(
    client: TestClient,
    monkeypatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("ENABLE_CODE2SESSION", "false")
    get_settings.cache_clear()
    response = client.post("/api/v1/auth/wx-login", json={"code": "temporary-code"})

    assert response.status_code == 404
    assert response.json()["code"] == "CODE2SESSION_DISABLED"
