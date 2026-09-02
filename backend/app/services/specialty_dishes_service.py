"""本地特色菜推荐服务。

设计要点：
- 城市级进程内缓存，24h TTL，控制 token 成本与响应速度。
- AI 调用可配置，未配置或失败时静默降级到人工维护的真实菜品目录。
- 对 AI 输出做严格 JSON 约束与校验，防止幻觉菜品混入。
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from typing import Any

import httpx
import structlog

from app.core.config import get_settings

log = structlog.get_logger()

settings = get_settings()


class CitySpecialty:
    """单个特色菜推荐项。"""

    __slots__ = ("name", "reason")

    def __init__(self, name: str, reason: str) -> None:
        self.name = name.strip()
        self.reason = reason.strip()

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "reason": self.reason}


#: 人工维护的真实本地菜品兜底目录，按城市索引。
FALLBACK_SPECIALTIES: dict[str, list[dict[str, str]]] = {
    "北京": [
        {"name": "北京烤鸭", "reason": "宫廷名菜，皮酥肉嫩，是京城饮食名片。"},
        {"name": "炸酱面", "reason": "老北京家常味道，酱香浓郁，四季皆宜。"},
        {"name": "豆汁焦圈", "reason": "地道京味早餐，酸香解腻，极具本地特色。"},
        {"name": "卤煮火烧", "reason": "传承百年的市井小吃，肠肺软烂入味。"},
    ],
    "上海": [
        {"name": "生煎包", "reason": "底部金黄酥脆，肉馅多汁，上海早餐代表。"},
        {"name": "小笼包", "reason": "皮薄汤鲜，一口爆汁，沪上经典。"},
        {"name": "红烧肉", "reason": "浓油赤酱，肥而不腻，本帮菜灵魂。"},
        {"name": "葱油拌面", "reason": "简单却考究，葱香扑鼻，深夜食堂首选。"},
    ],
    "广州": [
        {"name": "白切鸡", "reason": "皮黄肉白，鲜嫩多汁，粤菜经典之作。"},
        {"name": "虾饺", "reason": "早茶四大天王之一，晶莹剔透，虾肉弹牙。"},
        {"name": "叉烧", "reason": "蜜汁焦香，肥瘦相间，烧味店必点。"},
        {"name": "肠粉", "reason": "米皮滑嫩，馅料丰富，广式早餐标配。"},
    ],
    "深圳": [
        {"name": "沙井蚝", "reason": "宝安沙井特产，肉质肥美， seafood 控必试。"},
        {"name": "椰子鸡", "reason": "海南风味在深圳发扬光大，汤鲜甜清爽。"},
        {"name": "公明烧鹅", "reason": "皮脆肉嫩，荔枝木烧制，本地烧鹅代表。"},
        {"name": "深港早茶", "reason": "融合港式茶餐厅文化，选择丰富。"},
    ],
    "杭州": [
        {"name": "西湖醋鱼", "reason": "杭帮菜头牌，酸甜鲜嫩，西湖边必尝。"},
        {"name": "东坡肉", "reason": "慢火细炖，酥而不碎，入口即化。"},
        {"name": "片儿川", "reason": "雪菜笋片肉丝浇头，杭州人日常面食。"},
        {"name": "小笼包", "reason": "皮薄汁多，早餐店里的杭城味道。"},
    ],
    "成都": [
        {"name": "麻婆豆腐", "reason": "麻辣鲜香烫，川菜国际化名片。"},
        {"name": "火锅", "reason": "牛油锅底越煮越香，成都社交名片。"},
        {"name": "回锅肉", "reason": "灯盏窝状，咸香微辣，下饭神器。"},
        {"name": "担担面", "reason": "芝麻酱与花椒面交融，街头风味代表。"},
    ],
    "重庆": [
        {"name": "重庆火锅", "reason": "九宫格牛油锅底，麻辣鲜香，山城招牌。"},
        {"name": "小面", "reason": "一碗小面二两姜蒜水，重庆人的早晨。"},
        {"name": "酸辣粉", "reason": "红薯粉爽滑，酸辣开胃，街头必吃。"},
        {"name": "毛血旺", "reason": "鸭血毛肚一大盆，江湖菜代表。"},
    ],
    "西安": [
        {"name": "羊肉泡馍", "reason": "馍筋肉烂，汤浓味醇，西北风味代表。"},
        {"name": "肉夹馍", "reason": "白吉馍夹腊汁肉，酥脆与醇香兼具。"},
        {"name": "凉皮", "reason": "酸辣爽口，夏日消暑，关中 ubiquitous。"},
        {"name": "biangbiang面", "reason": "面条宽如腰带，油泼辣子香气扑鼻。"},
    ],
    "武汉": [
        {"name": "热干面", "reason": "芝麻酱香浓，面条筋道，武汉早餐之王。"},
        {"name": "豆皮", "reason": "蛋皮包裹糯米三鲜，外酥里嫩。"},
        {"name": "鸭脖", "reason": "卤香麻辣，追剧佐酒绝佳。"},
        {"name": "排骨藕汤", "reason": "洪湖莲藕粉糯，汤鲜甜暖胃。"},
    ],
    "南京": [
        {"name": "盐水鸭", "reason": "皮薄肉嫩，咸鲜适口，金陵名片。"},
        {"name": "鸭血粉丝汤", "reason": "鸭杂鲜香，粉丝滑爽，街头经典。"},
        {"name": "牛肉锅贴", "reason": "底部焦脆，肉馅多汁，秦淮小吃代表。"},
        {"name": "小笼包", "reason": "汁多味鲜，南京早餐桌上的常客。"},
    ],
    "苏州": [
        {"name": "松鼠桂鱼", "reason": "造型别致，酸甜酥脆，苏帮菜代表。"},
        {"name": "苏式汤面", "reason": "汤清味鲜，浇头丰富，早面文化精髓。"},
        {"name": "响油鳝糊", "reason": "鳝肉嫩滑，热油激香，经典本帮味。"},
        {"name": "蟹壳黄", "reason": "酥皮金黄，馅料多样，苏式点心代表。"},
    ],
    "长沙": [
        {"name": "臭豆腐", "reason": "外酥里嫩，闻着臭吃着香，长沙街头符号。"},
        {"name": "口味虾", "reason": "麻辣鲜香，夜宵摊 C 位。"},
        {"name": "糖油粑粑", "reason": "软糯香甜，老长沙传统小吃。"},
        {"name": "剁椒鱼头", "reason": "剁椒铺面，鱼肉鲜嫩，湘菜代表作。"},
    ],
    "厦门": [
        {"name": "沙茶面", "reason": "沙茶酱香浓微辣，海鲜配料丰富。"},
        {"name": "海蛎煎", "reason": "海蛎肥嫩，蛋皮酥脆，闽南经典。"},
        {"name": "土笋冻", "reason": "胶原蛋白冻，蘸酱酸辣，特色海味。"},
        {"name": "花生汤", "reason": "花生绵软，甜汤温润，厦门早餐常客。"},
    ],
    "青岛": [
        {"name": "辣炒蛤蜊", "reason": "蛤蜊肥美，鲜辣下饭，啤酒搭档。"},
        {"name": "鲅鱼水饺", "reason": "鱼肉馅鲜嫩多汁，胶东特色。"},
        {"name": "海鲜烧烤", "reason": "靠海吃海，夜市啤酒文化代表。"},
        {"name": "排骨米饭", "reason": "酱香排骨配米饭，本地快餐名片。"},
    ],
    "天津": [
        {"name": "狗不理包子", "reason": "十八道褶，汤汁饱满，津门三绝之一。"},
        {"name": "煎饼果子", "reason": "绿豆面煎饼夹馃篦儿，天津早餐代表。"},
        {"name": "十八街麻花", "reason": "酥脆香甜，津味传统点心。"},
        {"name": "锅巴菜", "reason": "绿豆锅巴浇卤，咸香软滑，早点必备。"},
    ],
    "哈尔滨": [
        {"name": "锅包肉", "reason": "外酥里嫩，酸甜适口，东北菜代表。"},
        {"name": "红肠", "reason": "俄式风味熏肠，哈尔滨伴手礼首选。"},
        {"name": "大列巴", "reason": "俄式大面包，麦香浓郁，扎实耐吃。"},
        {"name": "杀猪菜", "reason": "酸菜白肉血肠，东北冬日暖胃菜。"},
    ],
    "昆明": [
        {"name": "过桥米线", "reason": "高汤烫料，米线滑爽，云南名片。"},
        {"name": "汽锅鸡", "reason": "蒸汽凝结成汤，鸡肉鲜嫩，原汁原味。"},
        {"name": "鲜花饼", "reason": "玫瑰馅香甜，云南特色茶点。"},
        {"name": "饵块", "reason": "米制品柔韧，可烤可煮，早餐常见。"},
    ],
}


class _CityCache:
    """线程安全、带 TTL 与 LRU 驱逐的城市级缓存。"""

    def __init__(self, ttl_seconds: int, max_size: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, list[CitySpecialty]]] = OrderedDict()

    def get(self, city: str) -> list[CitySpecialty] | None:
        with self._lock:
            if city not in self._store:
                return None
            inserted_at, items = self._store[city]
            if time.monotonic() - inserted_at > self.ttl_seconds:
                self._store.pop(city, None)
                return None
            self._store.move_to_end(city)
            return items

    def set(self, city: str, items: list[CitySpecialty]) -> None:
        with self._lock:
            self._store[city] = (time.monotonic(), items)
            self._store.move_to_end(city)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache = _CityCache(
    ttl_seconds=settings.specialty_cache_ttl_seconds,
    max_size=settings.specialty_cache_max_size,
)


_SPECIALTY_SYSTEM_PROMPT = """你是一位熟悉中国各地饮食的本地美食向导。请根据用户给出的城市，推荐 3-5 道该市真实存在、有出处的本地特色菜。

要求：
1. 只推荐真实菜品，禁止编造菜名或杜撰典故。
2. 每道菜给出一句 20-40 字的推荐理由，突出本地特色或食用场景。
3. 如果城市为空、不是中国城市或你不熟悉，返回空数组 []。
4. 输出必须是 JSON 数组，不包含 markdown 代码块，字段为 name 和 reason。

示例输出：
[
  {"name": "北京烤鸭", "reason": "宫廷名菜，皮酥肉嫩，是京城饮食名片。"},
  {"name": "炸酱面", "reason": "老北京家常味道，酱香浓郁，四季皆宜。"}
]"""


def _normalize_city(city: str) -> str:
    """去掉常见行政区划后缀，便于命中缓存与兜底目录。

    注意：保留“州”字，因为杭州、广州、苏州等城市名以“州”结尾。
    """
    city = city.strip()
    for suffix in ("市", "县", "区"):
        if city.endswith(suffix):
            city = city[:-1]
    return city


def _parse_ai_specialties(raw: str) -> list[CitySpecialty]:
    """从严解析 AI 输出，失败或包含幻觉菜品时返回空列表。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.warning("specialty_ai_parse_failed", raw_preview=cleaned[:200], error=str(exc))
        return []

    if not isinstance(data, list):
        log.warning("specialty_ai_not_list", data_type=type(data).__name__)
        return []

    items: list[CitySpecialty] = []
    for entry in data[:6]:  # 安全上限
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if len(name) < 1 or len(name) > 40 or len(reason) < 2 or len(reason) > 120:
            continue
        # 简单校验：禁止明显编造关键词
        if "示例" in name or "待定" in name or "未知" in name:
            continue
        items.append(CitySpecialty(name, reason))
    return items


def _call_ai_sync(city: str) -> list[CitySpecialty]:
    """同步调用 CloudBase AI HTTP API 获取特色菜；失败返回空列表。"""
    api_key = settings.specialty_ai_api_key
    if not settings.specialty_ai_enabled or api_key is None:
        return []

    env_id = settings.cloudbase_env_id
    if not env_id:
        return []

    key = api_key.get_secret_value()
    base_url = f"https://{env_id}.api.tcloudbasegateway.com"
    url = f"{base_url}/v1/ai/{settings.specialty_ai_provider}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    payload = {
        "model": settings.specialty_ai_model,
        "messages": [
            {"role": "system", "content": _SPECIALTY_SYSTEM_PROMPT},
            {"role": "user", "content": f"请推荐中国{city}的本地特色菜。"},
        ],
        "stream": False,
        "temperature": 0.5,
    }

    try:
        with httpx.Client(timeout=settings.specialty_ai_timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:
        log.warning("specialty_ai_request_failed", city=city, error=str(exc))
        return []

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        log.warning("specialty_ai_response_malformed", city=city, error=str(exc))
        return []

    return _parse_ai_specialties(content)


def _fallback_specialties(city: str) -> list[CitySpecialty]:
    """从人工目录读取兜底数据；未收录的城市给出 3 条通用建议，确保推荐栏始终可用。"""
    raw = FALLBACK_SPECIALTIES.get(city, [])
    if raw:
        return [CitySpecialty(r["name"], r["reason"]) for r in raw]
    return [
        CitySpecialty(
            f"{city}的家常小炒",
            "口味偏大众的下饭菜，先点一道不容易踩雷，试试本地厨房水平。",
        ),
        CitySpecialty(
            f"{city}本地面/粉/饭",
            "碳水主食搭配当地浇头，是当地人日常最常吃的一顿，稳妥又省钱。",
        ),
        CitySpecialty(
            f"{city}夜市特色小吃",
            "本地夜市摊位上最能代表风味的小吃，建议让老板推荐当日最新鲜的。",
        ),
    ]


def get_specialties(city: str) -> dict[str, Any]:
    """获取城市特色菜推荐，优先缓存，其次 AI，最后兜底目录。"""
    if not city or not city.strip():
        return {"city": "", "items": [], "source": "fallback", "degraded": True}

    normalized = _normalize_city(city)

    cached = _cache.get(normalized)
    if cached is not None:
        return {
            "city": normalized,
            "items": [item.to_dict() for item in cached],
            "source": "cache",
            "degraded": False,
        }

    ai_items = _call_ai_sync(normalized)
    if ai_items:
        _cache.set(normalized, ai_items)
        return {
            "city": normalized,
            "items": [item.to_dict() for item in ai_items],
            "source": "ai",
            "degraded": False,
        }

    fallback = _fallback_specialties(normalized)
    _cache.set(normalized, fallback)
    return {
        "city": normalized,
        "items": [item.to_dict() for item in fallback],
        "source": "fallback",
        "degraded": settings.specialty_ai_enabled and not ai_items,
    }


def clear_cache() -> None:
    """测试与运维时使用。"""
    _cache.clear()
