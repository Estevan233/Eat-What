"""T08 今日上下文 API 集成测。

覆盖 PRD 验收：
1. GET /context/today 公开无需登录 → 200
2. 返回 TodayContext JSON 含所有字段
3. 同一天重复调用一致（缓存）
"""
def test_get_today_context_returns_full_payload(client):
    res = client.get("/api/v1/context/today")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]

    # TodayContext 必须字段
    assert "date" in data
    assert "solar_term_current" in data
    assert "solar_term_next_name" in data
    assert "solar_term_next_date" in data
    assert "zodiac_sign" in data
    assert "animal" in data
    assert "lunar_month" in data
    assert "lunar_day" in data
    assert "is_leap_month" in data

    # 字段类型校验
    assert isinstance(data["date"], str)
    assert isinstance(data["solar_term_current"], str)
    assert isinstance(data["solar_term_next_name"], str)
    assert isinstance(data["zodiac_sign"], str)
    assert isinstance(data["animal"], str)
    assert isinstance(data["lunar_month"], int)
    assert isinstance(data["lunar_day"], int)
    assert isinstance(data["is_leap_month"], bool)

    # 非空校验：任何时候都有下一节气名
    assert data["solar_term_next_name"]
    assert data["zodiac_sign"]
    assert data["animal"]


def test_get_today_context_no_auth_needed(client):
    """食物/上下文端点公开，不带 token 也能访问。"""
    res = client.get("/api/v1/context/today")
    assert res.status_code == 200
    assert res.json().get("code") != "AUTH_ERROR"


def test_get_today_context_calls_are_consistent(client):
    """同一天两次调用响应一致（缓存生效）。"""
    # 清缓存（路由走 cached 版本）
    from app.services.solar_terms import _get_today_context_cached
    _get_today_context_cached.cache_clear()

    r1 = client.get("/api/v1/context/today")
    r2 = client.get("/api/v1/context/today")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # 两次 data 完全相同
    assert r1.json()["data"] == r2.json()["data"]


def test_get_today_context_zodiac_value_in_12_signs(client):
    """zodiac_sign 必须在 12 星座英文键内。"""
    res = client.get("/api/v1/context/today")
    sign = res.json()["data"]["zodiac_sign"]
    assert sign in {
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
    }
