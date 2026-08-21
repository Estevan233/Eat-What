"""健康检查接口测试。"""


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["database"] == "configured"
    assert body["data"]["env"] == "dev"


def test_health_does_not_wake_the_database(client, monkeypatch):
    def unexpected_probe():
        raise AssertionError("liveness must not wake an auto-paused database")

    monkeypatch.setattr("app.db.check_database", unexpected_probe)

    res = client.get("/health")

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["data"]["database"] == "configured"


def test_health_has_request_id_header(client):
    res = client.get("/health")
    assert "x-request-id" in res.headers


def test_health_has_server_timing_header(client):
    res = client.get("/health")
    assert res.headers["server-timing"].startswith("app;dur=")
