# T08 节气与星座服务

## Goal

为推荐算法与 UI 提供「今天是什么节气、今天是什么星座、近期节气提示」等天文/历法上下文。所有计算在后端完成，前端只消费。

## Requirements

### Backend

#### 依赖

- `lunar-python ^3.2`（提供农历、节气、生肖、星座）

#### `app/services/solar_terms.py`

```python
from lunar_python import Solar, Lunar

def get_today_context(date: datetime | None = None) -> TodayContext:
    solar = Solar.fromDate(date or datetime.now())
    lunar = solar.getLunar()
    jq = lunar.getJieQi()              # 当前节气名（中文），可能为 ""（不在节气当天）
    next_jq = lunar.getNextJieQi()    # 下一个节气
    return TodayContext(
        date=date or datetime.now(),
        solar_term_current=jq,
        solar_term_next_name=next_jq.getName(),
        solar_term_next_date=next_jq.getSolar().toYmd(),
        zodiac_sign=compute_zodiac(solar),
        animal=lunar.getYearShengXiao(),  # 生肖
        lunar_month=lunar.getMonth(),
        lunar_day=lunar.getDay(),
        is_leap_month=bool(lunar.getMonth() > 0),
    )

def compute_zodiac(solar: Solar) -> str:
    """根据阳历日期返回星座英文键：aries/taurus/.../pisces"""
    m, d = solar.getMonth(), solar.getDay()
    # 标准 12 星座分界
    ...
```

12 星座分界日期表常量化在文件顶部。

#### `app/schemas/today_context.py`

- `TodayContext` Pydantic 模型，含上面所有字段

#### 路由 `app/api/v1/context.py`

- `GET /context/today` → 返回 `TodayContext`
- 公开接口（不需要登录，供首页天气卡片显示节气）
- 但天气 + 节气组合接口在 T09 后合并

#### 缓存

- `TodayContext` 每天可缓存一次（按日期 key），用 `lru_cache` 装饰器带日期参数即可
- 不引入 Redis

#### 测试

- `tests/services/test_solar_terms.py`：
  - 固定日期 `2026-07-23` → 预期 `zodiac_sign == "leo"`
  - 固定日期 `2026-02-04` → 预期 `solar_term_current` 含「立春」或下一节气名（具体由 lunar_python 输出，断言非空字符串）
  - 边界日期：1 月 20 日（摩羯/水瓶交界）

### Frontend

#### 类型同步

- `npm run gen:api` 后自动有 `TodayContext` 类型

#### UI 占位（本任务可以最小化）

- `src/components/WeatherBadge.vue`：显示 `{zodiac_sign} · {solar_term_current or '距<next>还有 X 天'}`
- today 页面顶部嵌入该组件
- 数据来源：调 `api.context.getToday()`（本任务可以建 `src/api/context.ts`）

## Acceptance Criteria

- [ ] `GET /context/today` 返回 `TodayContext` JSON
- [ ] 12 星座判定单测全绿
- [ ] 节气字段非空（即使在非节气日也应有下一节气名）
- [ ] 同一天内重复调用响应一致（缓存生效）
- [ ] 前端 today 页能显示星座与下一节气提示

## Dependencies

- T02（FastAPI 基础设施）

## Notes

- `lunar_python` 是离线计算，无需联网
- 不引入节气「七十二候」「物候」细化
- 星座 = 西方星座，不用中国「二十八宿」
- `compute_zodiac` 用阳历，星座边界用通用边界日期（部分年份可能差 1 天，可接受）
