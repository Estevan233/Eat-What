# T09 和风天气 API 接入

## Goal

为推荐算法与 UI 提供用户当前地理位置的实时天气数据。带 1 小时进程内缓存，避免被 API 限流。

## Requirements

### Backend

#### `app/services/weather_client.py`

```python
import httpx
from datetime import datetime
from app.core.config import get_settings
from app.core.errors import ExternalAPIError, RateLimitError

class WeatherClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.hefeng_api  # https://devapi.qweather.com/v7/weather/now
        self.api_key = self.settings.hefeng_key
        self._cache: dict[tuple[float, float], tuple[datetime, WeatherData]] = {}
        self._ttl = 3600  # 1h

    async def get_current(self, lat: float, lng: float) -> WeatherData:
        # 1. 缓存命中
        key = self._round_key(lat, lng)
        cached = self._cache.get(key)
        if cached and (datetime.utcnow() - cached[0]).total_seconds() < self._ttl:
            return cached[1]

        # 2. 调 API：先 location/lookup → 拿到 location id，再 weather/now
        location = await self._lookup_location(lat, lng)
        weather = await self._fetch_now(location.id)

        # 3. 缓存
        self._cache[key] = (datetime.utcnow(), weather)
        return weather

    async def _lookup_location(self, lat, lng) -> Location:
        # GET https://geoapi.qweather.com/v2/city/lookup?location={lng},{lat}
        ...

    async def _fetch_now(self, location_id: str) -> WeatherData:
        # GET https://devapi.qweather.com/v7/weather/now?location={id}&key={key}
        ...
```

#### schemas `app/schemas/weather.py`

```python
class WeatherData(BaseModel):
    location_name: str       # 城市/区县
    temp_c: int
    feels_like_c: int
    text: str                # 多云 / 晴 / 雨
    wind_dir: str
    wind_scale: str          # 1-3 级
    humidity: int
    weather_tag: str         # cold | hot | rainy | dry | mild — 由后端归类
    fetched_at: datetime
```

- `weather_tag` 是算法可用的离散值，由后端把和风文本映射到这 5 种 + `any`

#### 路由 `app/api/v1/context.py`（T08 已建）

- 扩展 `GET /context/today`：若已登录且有 profile.lat/lng（注意：UserProfile 不存位置，位置是实时的），调用前 `wx.getLocation` 拿位置传给后端
- 新增 `POST /context/weather`：
  - body: `{lat, lng}`
  - 返回 `WeatherData`
  - 已登录（防止滥用）

#### 位置合规

- 微信小程序：用户授权 `scope.userLocation` 后才能调 `wx.getLocation`
- 拒绝授权时：用默认 fallback（北京或上海）→ weather_tag = 'mild'
- 前端 UI 给出引导重新授权按钮

### Frontend

#### `src/composables/useLocation.ts`

- 按 spec 实现
- 暴露 `getLocation` action，包装 `wx.getLocation` 为 Promise
- 处理失败：返回 null + 设置 `permission_denied` 状态

#### `src/api/context.ts`

```ts
export const getWeather = (lat: number, lng: number) =>
  request<WeatherData>({ url: '/context/weather', method: 'POST', data: { lat, lng } })
```

#### `src/components/WeatherBadge.vue` 扩展

- today 页 `onShow`：调 `useLocation` + `getWeather` → 更新 weather 数据
- 失败时显示「点击授权位置」按钮

#### `src/stores/daily.ts`（部分提前实现）

- `weather: ref<WeatherData | null>`
- `fetchWeather()` action

### 测试

- `tests/services/test_weather_client.py`：
  - mock `httpx.AsyncClient`：location/lookup 返回 fixture、now 返回 fixture
  - 断言返回结构正确
  - 第二次调同坐标 → 缓存命中，不发请求
  - 429 → `RateLimitError`，500 → `ExternalAPIError`
- `tests/test_api_v1/test_context.py`：未登录 401、登录后返回 weather_tag

## Acceptance Criteria

- [ ] 已登录 + 已授权位置的用户，today 页能显示当前天气（温度 + 文字描述 + weather_tag）
- [ ] 同坐标 1 小时内第二次请求不发外部 API（log 验证）
- [ ] 拒绝位置授权时，UI 引导重新授权，不崩溃
- [ ] 和风 API 429 时返回 429 给前端，UI 提示「天气服务繁忙」
- [ ] `weather_tag` 在 `{cold, hot, rainy, dry, mild, any}` 中
- [ ] pytest 全绿

## Dependencies

- T02（FastAPI 基础设施、errors）
- T08（context 路由模块）

## Notes

- 和风天气开发版 key 必须填到 `.env` 的 `HEFENG_KEY`
- 开发版限 1000 次/天，有缓存后单用户每天 1 次足够
- 不实现历史天气
- 不实现分钟级降雨（不在 MVP 范围）
- 城市映射失败的 fallback：用坐标直查 now 接口（和风支持坐标）
