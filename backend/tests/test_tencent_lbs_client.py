"""腾讯位置服务客户端的纯逻辑测试 - 不打外部网络。

覆盖：
- 缓存键网格化（3 位小数，约 100-200m）：节流的核心，同商圈不重复扣配额
- 响应解析：字段映射、非法项跳过、data 非法时报 ExternalAPIError
"""
import pytest

from app.core.errors import ExternalAPIError
from app.services.tencent_lbs_client import TencentLbsClient


def _client() -> TencentLbsClient:
    return TencentLbsClient(api_key="test-key", timeout=1.0)


def test_cache_key_rounds_to_grid_and_includes_keyword_radius() -> None:
    key = TencentLbsClient._cache_key("美食", 39.89631551, 116.323459711, 1000)
    assert key == ("美食:39.896,116.323", 1000)


def test_cache_key_distinguishes_keyword_and_radius() -> None:
    base = TencentLbsClient._cache_key("美食", 39.8963, 116.3234, 1000)
    assert TencentLbsClient._cache_key("火锅", 39.8963, 116.3234, 1000) != base
    assert TencentLbsClient._cache_key("美食", 39.8963, 116.3234, 2000) != base


def test_parse_maps_fields_and_skips_invalid_items() -> None:
    client = _client()
    payload = {
        "status": 0,
        "data": [
            {
                "title": "示例餐厅",
                "address": "示例路 1 号",
                "category": "美食;中餐厅",
                "location": {"lat": 39.9, "lng": 116.32},
                "_distance": 350,
            },
            {"title": "缺坐标的店"},
            "not-a-dict",
        ],
    }

    result = client._parse(payload)

    assert result.provider_available is True
    assert result.source == "tencent_lbs"
    assert len(result.shops) == 1
    shop = result.shops[0]
    assert shop.name == "示例餐厅"
    assert shop.address == "示例路 1 号"
    assert shop.category == "美食;中餐厅"
    assert shop.lat == 39.9
    assert shop.lng == 116.32
    assert shop.distance_m == 350


def test_parse_rejects_non_list_data() -> None:
    client = _client()
    with pytest.raises(ExternalAPIError):
        client._parse({"status": 0, "data": {"unexpected": "object"}})
