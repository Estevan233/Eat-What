"""健康检查接口测试。"""


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["database"] == "ready"
    assert body["data"]["env"] == "dev"


def test_health_database_unavailable(client, monkeypatch):
    monkeypatch.setattr("app.main.check_database", lambda: False)

    res = client.get("/health")

    assert res.status_code == 503
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["data"] == {
        "status": "degraded",
        "database": "unavailable",
    }


def test_health_has_request_id_header(client):
    res = client.get("/health")
    assert "x-request-id" in res.headers
