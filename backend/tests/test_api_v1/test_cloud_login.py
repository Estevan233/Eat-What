"""CloudBase 私有链路登录契约测试。"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.user import User


def _headers(**overrides: str) -> dict[str, str]:
    values = {
        "X-WX-OPENID": "openid-cloud-user",
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "cloud-test",
        "X-WX-REQUEST-ID": "request-123",
    }
    values.update(overrides)
    return values


def test_cloud_login_creates_and_reuses_user(client: TestClient, session) -> None:
    first = client.post("/api/v1/auth/cloud-login", headers=_headers())
    second = client.post("/api/v1/auth/cloud-login", headers=_headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]
    assert first.json()["data"]["token"]
    assert first.json()["data"]["user"]["profile_complete"] is False
    assert first.json()["data"]["user"]["account_kind"] == "wechat"
    assert first.json()["data"]["merge_status"] == "not_requested"

    user_id = first.json()["data"]["user"]["id"]
    db_user = session.get(User, user_id)
    assert db_user is not None
    assert db_user.account_kind == "wechat"
    assert db_user.account_status == "active"


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


def test_cloud_login_merges_authenticated_guest_and_is_retry_safe(
    client: TestClient,
    session,
) -> None:
    guest_login = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "cloud-upgrade-guest", "nickname": "游客饭饭"},
    ).json()["data"]
    guest_id = guest_login["user"]["id"]
    headers = {
        **_headers(),
        "Authorization": f"Bearer {guest_login['token']}",
    }

    first = client.post("/api/v1/auth/cloud-login", headers=headers)
    second = client.post("/api/v1/auth/cloud-login", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["merge_status"] == "completed"
    assert second.json()["data"]["merge_status"] == "completed"
    assert first.json()["data"]["user"]["account_kind"] == "wechat"
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]

    source = session.get(User, guest_id)
    assert source is not None
    assert source.account_status == "merged"
    assert source.merged_into_user_id == first.json()["data"]["user"]["id"]


def test_cloud_login_rejects_invalid_existing_bearer(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/cloud-login",
        headers={**_headers(), "Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_ERROR"


def test_cloud_login_rejects_switching_from_another_wechat_session(
    client: TestClient,
    session,
) -> None:
    other = User(openid="different-wechat-openid", account_kind="wechat")
    session.add(other)
    session.commit()
    session.refresh(other)
    assert other.id is not None

    response = client.post(
        "/api/v1/auth/cloud-login",
        headers={
            **_headers(),
            "Authorization": f"Bearer {create_access_token(other.id)}",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "SESSION_IDENTITY_CONFLICT"


@pytest.mark.parametrize(
    ("account_kind", "account_status"),
    [("guest", "active"), ("wechat", "merged")],
)
def test_cloud_login_rejects_inconsistent_existing_account(
    client: TestClient,
    session,
    account_kind: str,
    account_status: str,
) -> None:
    user = User(
        openid="openid-cloud-user",
        account_kind=account_kind,
        account_status=account_status,
    )
    session.add(user)
    session.commit()

    response = client.post("/api/v1/auth/cloud-login", headers=_headers())

    assert response.status_code == 409
    assert response.json()["code"] == "ACCOUNT_STATE_CONFLICT"
    session.refresh(user)
    assert user.account_kind == account_kind
    assert user.account_status == account_status


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
