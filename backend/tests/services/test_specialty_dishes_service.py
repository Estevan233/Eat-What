"""本地特色菜推荐服务测试。"""

from unittest.mock import MagicMock, patch

import pytest

from app.services import specialty_dishes_service as svc


def test_normalize_city_strips_suffixes():
    assert svc._normalize_city("杭州市") == "杭州"
    assert svc._normalize_city("北京") == "北京"
    assert svc._normalize_city("  成都市 ") == "成都"


def test_fallback_specialties_returns_known_city():
    items = svc._fallback_specialties("杭州")
    assert len(items) >= 3
    assert any(item.name == "西湖醋鱼" for item in items)


def test_fallback_specialties_returns_empty_for_unknown_city():
    # 现在未收录城市会返回 3 条通用建议，确保推荐栏始终可见。
    items = svc._fallback_specialties("不存在的城市")
    assert len(items) == 3
    assert all(item.name and item.reason for item in items)


def test_parse_ai_specialties_extracts_valid_json():
    raw = '[{"name": "A", "reason": "好吃"}, {"name": "B", "reason": "不错"}]'
    items = svc._parse_ai_specialties(raw)
    assert [item.to_dict() for item in items] == [
        {"name": "A", "reason": "好吃"},
        {"name": "B", "reason": "不错"},
    ]


def test_parse_ai_specialties_strips_markdown_code_block():
    raw = '```json\n[{"name": "A", "reason": "好吃"}]\n```'
    items = svc._parse_ai_specialties(raw)
    assert len(items) == 1


def test_parse_ai_specialties_filters_invalid_entries():
    raw = '[{"name": "A", "reason": "好吃"}, {"name": "", "reason": "x"}, {"name": "示例菜", "reason": "这是示例"}]'
    items = svc._parse_ai_specialties(raw)
    assert len(items) == 1
    assert items[0].name == "A"


def test_parse_ai_specialties_returns_empty_on_bad_json():
    assert svc._parse_ai_specialties("not json") == []


def test_get_specialties_uses_fallback_and_caches():
    svc.clear_cache()
    result = svc.get_specialties("杭州")
    assert result["city"] == "杭州"
    assert len(result["items"]) > 0
    assert result["source"] == "fallback"

    # 第二次命中缓存
    cached = svc.get_specialties("杭州市")
    assert cached["source"] == "cache"
    assert cached["items"] == result["items"]


def test_get_specialties_empty_city_degrades():
    result = svc.get_specialties("   ")
    assert result["items"] == []
    assert result["degraded"] is True


def test_get_specialties_ai_success_caches_ai_result():
    svc.clear_cache()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '[{"name": "龙井虾仁", "reason": "茶香去腥"}]'}}]
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        with patch.object(svc.settings, "specialty_ai_enabled", True):
            with patch.object(svc.settings, "cloudbase_env_id", "cloud1-test"):
                with patch.object(svc.settings, "specialty_ai_api_key", MagicMock(get_secret_value=lambda: "key")):
                    result = svc.get_specialties("杭州")

    assert result["source"] == "ai"
    assert result["items"][0]["name"] == "龙井虾仁"


def test_get_specialties_ai_failure_silently_falls_back():
    svc.clear_cache()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = RuntimeError("network down")
        mock_client_cls.return_value = mock_client

        with patch.object(svc.settings, "specialty_ai_enabled", True):
            with patch.object(svc.settings, "cloudbase_env_id", "cloud1-test"):
                with patch.object(svc.settings, "specialty_ai_api_key", MagicMock(get_secret_value=lambda: "key")):
                    result = svc.get_specialties("杭州")

    assert result["source"] == "fallback"
    assert len(result["items"]) > 0
    assert result["degraded"] is True


def test_cache_respects_ttl(monkeypatch):
    svc.clear_cache()
    svc._cache.set("杭州", [svc.CitySpecialty("A", "B")])
    assert svc._cache.get("杭州") is not None

    # 伪造已过期
    future = svc.time.monotonic() + svc._cache.ttl_seconds + 1
    monkeypatch.setattr(svc.time, "monotonic", lambda: future)
    assert svc._cache.get("杭州") is None


def test_cache_lru_eviction():
    svc.clear_cache()
    svc._cache.max_size = 2
    svc._cache.set("a", [svc.CitySpecialty("a", "1")])
    svc._cache.set("b", [svc.CitySpecialty("b", "2")])
    svc._cache.set("c", [svc.CitySpecialty("c", "3")])
    assert svc._cache.get("a") is None
    assert svc._cache.get("b") is not None
    assert svc._cache.get("c") is not None
