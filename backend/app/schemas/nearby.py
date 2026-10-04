"""附近店铺数据 schema - 地图选点后的附近 POI 参考。

学习点：
- provider_available=false 时 shops 为空，UI 展示"暂不可用"而不是编造结果
- anchor 是"当次锚点"：服务端只用坐标做搜索，不落库（PRD R6）
- 字段命名后端 snake_case，前端 camelCase 由 request 层转换
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NearbyShop(BaseModel):
    """一家附近店铺的最小展示字段。"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="POI 名称")
    address: str = Field(description="详细地址")
    category: str = Field(default="", description="POI 分类，如 '美食;中餐厅'")
    lat: float = Field(description="纬度 gcj02")
    lng: float = Field(description="经度 gcj02")
    distance_m: int = Field(default=0, ge=0, description="距锚点直线距离（米）")


class NearbyShopsRequest(BaseModel):
    """POST /nearby/shops 请求体。lat/lng 为 gcj02（与 map 组件一致）。"""

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    keyword: str = Field(default="美食", max_length=20, description="搜索关键词")
    radius_m: int = Field(default=1000, ge=100, le=5000, description="搜索半径（米）")


class NearbyShopsResponse(BaseModel):
    """附近店铺响应。source=cache 或 is_stale=true 时前端可标注"缓存结果"。"""

    provider_available: bool = Field(
        default=True,
        description="腾讯位置服务是否可用；false 时 shops 必为空",
    )
    source: str = Field(default="tencent_lbs", description="tencent_lbs / cache / unavailable")
    is_stale: bool = False
    anchor_name: str = Field(default="", description="锚点名称，来自腾讯地点搜索返回")
    shops: list[NearbyShop] = Field(default_factory=list)
    fetched_at: datetime
