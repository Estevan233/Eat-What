# T11 今日推荐 UI + 历史记录 + 收藏

## Goal

把推荐算法的结果可视化到首页，并实现用户「选择今天的菜 → 写入历史」与「收藏」的闭环。

## Requirements

### Backend

#### 数据模型

```python
# app/models/daily.py
class DailyLog(SQLModel, table=True):
    __tablename__ = "daily_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    date: str = Field(max_length=10, index=True)             # YYYY-MM-DD
    mood: str = Field(max_length=16)
    weather_snapshot_json: dict = Field(default={}, sa_column=Column(JSON))
    recommended_food_ids_json: list[int] = Field(default=[], sa_column=Column(JSON))
    chosen_food_id: Optional[int] = Field(default=None, foreign_key="foods.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_user_date"),)

# app/models/favorite.py
class Favorite(SQLModel, table=True):
    __tablename__ = "favorites"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    food_id: int = Field(foreign_key="foods.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "food_id", name="uq_fav_user_food"),)
```

#### 路由 `app/api/v1/daily.py` 扩展

- `POST /daily/recommend` → 推荐（T10 已实现）
- `POST /daily/choose` body `{food_id: int, mood: str}` → 写入/更新今天的 `DailyLog`，返回 `DailyLogRead`
- `GET /daily/today` → 返回今天的 DailyLog（不存在返回 null）
- `GET /daily/history?days=30` → 近 30 天日志

#### 路由 `app/api/v1/favorite.py`

- `POST /favorite/{food_id}` → 收藏
- `DELETE /favorite/{food_id}` → 取消
- `GET /favorite` → 分页列表，含 Food 详情

#### service `app/services/daily_service.py`、`favorite_service.py`

- upsert_today_log
- get_recent（T10 已用）
- toggle_favorite
- list_favorites

#### 测试

- `tests/test_api_v1/test_daily.py`：choose / today / history
- `tests/test_api_v1/test_favorite.py`：toggle、重复收藏 idempotent、列表

### Frontend

#### `src/pages/today/today.vue`

布局（自上而下）：

1. **顶部状态栏**：`<WeatherBadge>` 显示 `{星座} · {节气} · {天气描述} {temp}°`
2. **心情选择器**：5 个 chip（开心/平常/疲惫/压力/焦虑），点击切换
3. **活动量选择器**：3 个 chip（轻松/平常/高强度）
4. **「看看今天吃啥」主按钮**：
   - 调 `useLocation` → 拿到位置
   - 调 `POST /daily/recommend` with mood/activity/lat/lng
   - 显示骨架屏
5. **推荐结果**：3 张 `<FoodCard>` 卡片
   - 每张：菜名、烹饪方法、卡路里、tags chip
   - 卡片下方展开「为什么推荐」理由文本
   - 卡片操作：「就吃这个」按钮（→ POST /daily/choose）、「收藏」图标按钮
6. **今日已选**：若今天 DailyLog.chosen_food_id 存在，顶部显示「今天你选了：xxx」，可重新生成推荐
7. **下拉刷新**：调 `onPullDownRefresh` 重新跑 recommend

#### `src/components/FoodCard.vue`

- props: `food: FoodWithReason`、`chosen: boolean`
- emits: `choose(food)`、`favorite(food)`
- 展示理由文本（折叠/展开）

#### `src/stores/daily.ts`

- 状态：`recommendation`、`todayLog`、`weather`、`mood`、`activityLevel`、`loading`
- actions：`fetchRecommend()`、`chooseFood(id)`、`fetchTodayLog()`、`refreshWeather()`

#### `src/stores/favorite.ts`

- 状态：`favorites: Food[]`、`loading`、`cached_at`
- actions：`toggle(food)`、`fetchList()`、`isFavorited(id)`

#### `src/pages/history/history.vue`

- 列表展示近 30 天 DailyLog
- 每条：日期、心情图标、选中的菜名（点击进菜详情）
- 长按删除（可选）

#### `src/pages/favorite/favorite.vue`（新增非 tabBar 页）

- 收藏列表
- 每条展示菜名 + 取消收藏按钮

#### `src/pages/food/detail.vue`（可选）

- `GET /food/{id}` 详情页，从 FoodCard 跳转过去

## Acceptance Criteria

- [ ] 首次进入 today：未选过菜 → 显示选择器 + 主按钮 → 点击 → 拉推荐 → 展示 3 张卡片
- [ ] 选择心情切换按钮能影响下次推荐（再次点击主按钮验证）
- [ ] 点击「就吃这个」→ toast「已记录今日选择」→ 顶部状态变「今天你选了 xxx」
- [ ] 第二天进入 today：能看到昨天的历史记录
- [ ] 收藏图标点击后变实心 + 写入后端，再点取消
- [ ] 历史页能看到近 30 天的日志
- [ ] 收藏页能看到所有收藏
- [ ] 下拉刷新能重新生成推荐
- [ ] 网络断开时 today 页给出提示但不崩溃
- [ ] 后端 pytest 全绿，前端 lint/type-check 全绿

## Dependencies

- T04（登录态）
- T10（推荐算法与 `/daily/recommend` 接口）

## Notes

- 本任务涉及大量 UI，建议分小段实现：先 recommend 调用 → FoodCard 渲染 → choose → 收藏 → 历史
- `recommend` 接口每次都重新算，不缓存（用户可手动刷新）
- `DailyLog` 每天每用户一条，用 `(user_id, date)` 唯一约束
- `Favorite` 重复收藏用 `INSERT OR IGNORE` 或先 SELECT 后判断
- 不实现菜谱步骤详情（P1 范围）
