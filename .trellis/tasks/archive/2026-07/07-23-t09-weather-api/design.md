# T09 Design — 天气 API 接入

## 1. 偏离 PRD 的原因

PRD 原方案用和风天气（HEFENG_KEY + `devapi.qweather.com`）。调研发现：

1. **和风 API 已迁移鉴权方式**：2026 年起公共 API 域名（含 `devapi.qweather.com` /
   `geoapi.qweather.com`）逐步停用，需切换为用户专属 `API Host`（形如
   `abc123.qweatherapi.com`）+ **JWT/Ed25519 鉴权**。沿用旧 `?key=` 查询参数 → `403 Invalid Host`。
2. **JWT 接入成本高**：本地生成 Ed25519 密钥对 → 上传公钥到和风控制台 → 后端用私钥签 JWT →
   Authorization: Bearer。额外依赖 cryptography，且 key 与控制台配置耦合。
3. **Open-Meteo 是更轻、更准的替代**：
   - **免注册、免 Key、免 Host**：直接 `GET api.open-meteo.com/v1/forecast` 即可。
   - **同源数据更准**：融合 **CMA GRAPES**（中国气象局数据）+ ECMWF + NOAA GFS + DWD ICON +
     MeteoFrance 等 17 个国家气象模型，default 「Best Match」自动选该地区最优模型。
     实际等同微软天气（用户反馈"最准"的同源上游）。
   - **MIT 开源、可商用**，开源仓库 26k+ stars。
   - **响应简洁**：JSON 直出温度/湿度/体感/WIND/WMO weather_code，坐标直查无需先查 city id。
4. **测试无依赖**：单测打 httpx mock 即可覆盖，E2E 真调用也稳定免费。

**决策**：用 **Open-Meteo 替代和风**。在 `WeatherProvider` 抽象上保持适度向前兼容
（service 接口稳定，未来若需切换他源仅改 client 实现），但 **不在 MVP 引入多 Provider
分发**——只实现一个 `OpenMeteoClient`。

## 2. Open-Meteo 接入细节

### 端点

`GET https://api.open-meteo.com/v1/forecast`

### 请求参数（坐标 + current 天气变量）

| 参数 | 值 | 含义 |
|---|---|---|
| `latitude` | float | WGS84 纬度 |
| `longitude` | float | WGS84 经度（亚洲正经，美洲负） |
| `current` | 逗号分隔的变量列表 | 一次性拿当前实况 |
| `timezone` | `Asia/Shanghai` | 让返回时间戳本地化 |
| `temperature_unit` | `celsius` | 默认 |
| `wind_speed_unit` | `kmh` | 默认 |

`current` 变量列表（推荐 MVP 取这些）：
- `temperature_2m`：温度（°C）
- `relative_humidity_2m`：湿度（%）
- `apparent_temperature`：体感温度（°C）
- `weather_code`：WMO 标准代码（0=晴, 1-3=多云, 45/48=雾, 51-67=雨, 71-77=雪, 80-82=阵雨, 95-99=雷暴）
- `wind_speed_10m`：风速（km/h）
- `wind_direction_10m`：风向（°，0/360=北，90=东）
- `precipitation`：当前小时降水（mm）

### 响应结构（实测，北京 116.41, 39.92）

```json
{
  "latitude": 39.964848, "longitude": 116.39665,
  "timezone": "Asia/Shanghai", "utc_offset_seconds": 28800,
  "elevation": 49.0,
  "current_units": {"temperature_2m": "°C", ...},
  "current": {
    "time": "2026-07-31T12:00",
    "interval": 900,
    "temperature_2m": 32.7,
    "relative_humidity_2m": 61,
    "apparent_temperature": 37.6,
    "weather_code": 51,
    "wind_speed_10m": 8.5,
    "wind_direction_10m": 193
  }
}
```

## 3. WeatherData 字段（后端格式）

```python
class WeatherData(BaseModel):
    location_name: str          # "Open-Meteo @ lat,lng"（Open-Meteo 不返城市名）
    temp_c: float               # 当前温度（°C）
    feels_like_c: float         # 体感温度
    text: str                   # "晴 / 多云 / 小雨 / 雪 / 阵雨 / 雷暴" 由 WMO code 映射
    wind_dir: str              # "北 / 东北 / 东 / ..." 由 wind_direction_10m (deg) 映射
    wind_scale: str            # "1-3级" 由 wind_speed_10m (km/h) 映射蒲福风级
    humidity: int             # %
    precipitation_mm: float   # 当前小时降水
    weather_tag: Literal[
        "cold", "hot", "rainy", "dry", "snowy", "mild", "any"
    ]
    fetched_at: datetime
```

新增 `snowy`（PRD 5 个不够：雪天应单列），共 6+1 个 tag。

### weather_tag 归类规则

按优先级（每条独立判断，互斥取第一个命中）：

1. `snowy`：WMO code 在 {71,73,75,77,85,86} 之一，或日降水 > 5mm 且气温 < 0°C
2. `rainy`：WMO code 在 {51-67, 80-82, 95-99}，或 precipitation > 0.5mm
3. `cold`：temp_c < 10
4. `hot`：temp_c >= 28
5. `dry`：humidity < 35 且 precipitation = 0
6. `mild`：上述都不命中（默认温和）
- 服务异常 → 调用方拿 `weather_tag = "any"` 作 fallback

## 4. 缓存策略

进程内 dict + TTL，跟 PRD 一致：
- key：(round_lat, round_lng) 6 位小数精度（~11m 范围足够）
- value：(fetched_at, WeatherData)
- TTL：3600s（1 小时），PRD 同
- 命中验证：缓存命中时**不发 HTTP**，E2E 用 mock httpx 断言 `n_requests == 1`

## 5. 路由

### `POST /context/weather`（新增，登录后）

```python
@router.post("/weather", response_model=dict[str, Any])
def get_weather_route(
    body: WeatherRequest,         # {lat: float, lng: float}
    user: User = Depends(get_current_user),     # 登录必需（PRD：防滥用）
) -> dict[str, object]:
    data = weather_client.get_current(body.lat, body.lng)
    return success(data=data.model_dump(mode="json"))
```

body 校验：lat ∈ [-90, 90]，lng ∈ [-180, 180]，浮点。

### 前端位置合规

- 调 `wx.getLocation({type: 'wgs84'})` 拿 lat/lng
- 用户拒绝授权：UI 显示「点击授权位置」按钮，**不调后端**（后端没坐标也调不了）
- 用户授权：调 `getWeather(lat, lng)` → 显示天气

## 6. 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 天气 API | Open-Meteo 替代和风 | 同源（CMA GRAPES/ECMWF）+免 Key+免Host+MIT |
| weather_tag | 6+1（PRD 5+1）+ snowy | 雪天对推荐有显著影响，单列 |
| 缓存粒度 | 坐标 6 位小数 | ~11m 精度，避免近邻坐标重复打 |
| 城市名 | "Open-Meteo @ lat,lng" | Open-Meteo 不返城市名，前端不依赖 |
| 风向映射 | 自实现 deg→8 方位 | 不引外部库 |
| 风速等级 | 蒲福风级 0-12 | 描述更可读 |
| Provider 抽象 | 单 OpenMeteoClient | MVP 不引入多 provider 分发 |