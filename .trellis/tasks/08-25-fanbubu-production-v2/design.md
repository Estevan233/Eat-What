# 技术设计

## 1. 总体边界

```text
uni-app / Vue 3 小程序
  ├─ CloudTransport -> wx.cloud.callContainer -> FastAPI
  ├─ CloudBase Storage -> 用户主动选择的头像
  └─ wx.cloud.extend.AI -> 仅解析 MealIntent（可关闭）

FastAPI / Cloud Run
  ├─ trusted CloudBase identity headers -> JWT
  ├─ rule recommender + bounded personalization
  ├─ QWeather -> fresh/stale cache -> neutral
  └─ Repository -> CloudBase HTTP 数据网关 -> MySQL 数据表
```

现有 HTTP Repository 是唯一生产数据访问路径。天气第三方 API 与数据库 HTTP 网关是两条完全不同的网络依赖，不能再把“公网 MySQL”“HTTP 数据网关”“天气公网出访”搅成一锅粥。

## 2. 身份与资料

### 2.1 登录状态机

1. 小程序初始化 CloudBase 环境并调用 `/auth/cloud-login`。
2. 后端验证 `X-WX-OPENID/X-WX-APPID/X-WX-ENV`，upsert User，签发 JWT。
3. 前端原子保存 token 与 UserRead，此刻认证已经完成。
4. `needsProfileCompletion = !avatarUrl || nickname in {"微信用户", "用户"}`。
5. 非游客且本设备未跳过时展示资料完善卡/底部面板；保存或跳过都进入首页。

这与参考文章的底层顺序一致——先建立微信身份再签发业务令牌——但不照抄其过时的 `getUserInfo` 头像昵称获取方式。头像昵称属于用户主动填写的公开资料，不是 openid 身份凭证。

### 2.2 接口与存储

- 新增 `PATCH /api/v1/profile/account`，请求 `{nickname?, avatar_url?}`，至少一个字段。
- nickname 去首尾空白，长度 1–64；avatar 只接受 `cloud://` 或 `https://`，长度不超过现有模型上限。
- 响应复用 AuthUserRead，并以加法字段 `profile_complete` 保持旧客户端兼容。
- 头像先由小程序上传到 `avatars/{userId}/{contentHash}.{ext}`，仅把 fileID 发给后端；上传失败不清会话。
- 前端保存成功后同时更新 Pinia 与持久会话。跳过标记只放设备本地 `profile_onboarding_dismissed_v1:{userId}`，Mine 页仍可编辑。

## 3. 菜谱与个性化

### 3.1 数据质量

把现有校验器从固定 60 提升到固定 120，并新增：

- 角色严格为 `main=50, vegetable=50, staple=20`；
- `prep_time_min/cook_time_min/servings/version` 合法；
- 主料、肉蛋水产、用油必须量化，调味料才可“适量”；
- 肉蛋水产的步骤必须出现煮、蒸、炒、炖、煎至熟等熟制语义；
- 每份能量与三大营养素为正且处于家庭菜谱合理上界；
- source URL 仅 HTTPS；营养依据必填；禁止疗效承诺关键词。

新增 60 条优先从现有 145 条非 recipe-ready 食物中选择，避免修改 Food 主键。导入仍按稳定 food name 幂等 upsert，不清表。另生成 `recipe_review_manifest.json`，记录新增项、来源、人工审阅状态与备注；它是审计材料，不进入运行 API。

### 3.2 有界个性化

现有规则分与硬过滤保持权威。新增 `PreferenceSnapshot`：

- 近 7 日选择/曝光：继续产生强新鲜度惩罚；
- 收藏：同食材/品类小幅正向偏好，不直接把收藏菜反复顶到第一；
- 已选择历史：学习常用 cooking_method/食材，单项调整受 `preference_history` 权重上限约束；
- 用户稳定探索种子：`sha256(user_id + event_date + request_id + meal_role + engine_version)`。

选择步骤先按最终分取“距本角色最高分不超过 5 分”的质量带，再用稳定种子做加权抽样；同一个 request_id 可复现，不同 request_id/用户产生差异。若质量带候选不足，回退现有确定性选择。算法只改变软排序，不改变硬过滤、角色结构和营养校验。

## 4. 天气容错

### 4.1 组件

- `QWeatherClient`：`GET https://{QWEATHER_API_HOST}/v7/weather/now`，`location=lng,lat`（最多两位小数），Header `X-QW-Api-Key`。
- `QWeatherClient` 同时负责单供应商调用、同城网格缓存、时间预算、来源标记与降级；当前版本不实现第二 provider。

### 4.2 时间预算与缓存

一次推荐不能被两个第三方 API 串行拖成“加载动画观赏大会”。默认预算：

- 新鲜缓存 TTL 60 分钟；陈旧缓存上限 12 小时；坐标按 0.1° 网格化作为 key，降低调用量且不落精确位置。
- QWeather 总超时 2.5 秒，推荐服务层上限 3 秒；不在一次用户请求内串行重试第二供应商。
- 成功即写 last-good；失败读 stale；无 stale 返回 neutral。
- 结构化日志只写 provider、阶段、异常类、耗时、粗粒度网格与 request id，不写 key 和完整坐标。

WeatherData 新增字段有默认值，旧快照仍可反序列化：`source=qweather|cache|neutral`、`is_stale`、`observed_at?`。前端只缓存 providerAvailable 的真实结果。

## 5. AI 用餐意图

### 5.1 合同

```text
MealIntent
  availableIngredients: string[0..12]
  excludedIngredients: string[0..12]
  maxTimeMinutes: 5..180 | null
  goal: balanced | weight_control | high_protein | null
  diningModeHint: cook | eat_out | null
  summary: string <= 80
```

前端模型提示词只要求从用户文本抽取 JSON，不要求生成菜名或健康结论。解析器剥离 Markdown fence 后严格验证，未知字段丢弃，越界整体失败。成功后用户可以看见并删除解析出的标签，再提交推荐。

RecommendRequest 新增可选 `meal_intent`。后端再次验证：`excludedIngredients` 进入食材硬过滤；`availableIngredients`、时间与目标进入有限软评分；`diningModeHint` 只预填 UI，不能覆盖用户最终点击的模式。

### 5.2 开关与降级

- 代码调用 CloudBase 原生 `wx.cloud.extend.AI`，不放 API key。
- `VITE_AI_MEAL_INTENT_ENABLED` 只是非秘密功能开关；模型组/模型 ID 也是公开配置，但必须与控制台已开启模型一致。
- 实施前执行 CloudBase AI 额度与模型可用性预检；未通过时默认关闭入口。
- AI 调用、解析、网络任一失败均显示可重试提示，保留原文本且不阻断手动推荐。

## 6. UI 设计

沿用已上线的暖白背景、品牌橙、圆角白卡、现有字号与 TabBar，不做第二套视觉系统。

- 登录后资料完善：一张紧凑卡/底部面板，标题“让饭卜卜认识你”，头像按钮、昵称输入、主按钮“保存并继续”、文字按钮“先跳过”。
- Mine：头像昵称区域可点击进入同一编辑面板。
- Today：在用餐设置和推荐按钮之间增加单行自然语言输入，示例“冰箱有番茄鸡蛋，20 分钟，少油”；解析结果展示为可删除标签。
- 天气 Badge：实时不加噪声；缓存显示“缓存天气”；完全不可用显示“天气暂不可用”，但不抢占推荐主任务。

不新增一排花里胡哨的 AI 图标，也不把助手做成全屏聊天页。MVP 的价值是少点两下就决定吃什么，不是让用户和机器人进行一场关于番茄炒蛋的哲学辩论。

## 7. 兼容与发布

- 所有请求字段均可选，旧小程序请求继续成功。
- 所有响应新增字段均提供默认值，现有缓存可读。
- 数据库只需在确有模型字段新增时走 Alembic/HTTP 网关迁移；资料完成状态采用计算字段，本任务不为“跳过”新增表列。
- 天气凭据缺失时启动可运行但记录 provider disabled；生产发布验收要求 QWeather 两项配置同时存在。
- AI 默认关闭，只有真实环境预检和模拟器测试通过后才在发布构建打开。
- 云托管与小程序上传都属于部署闸门，必须在本地全绿、变更清单审阅并由用户再次确认后执行。

## 8. 回滚

- 登录资料：关闭前端入口即可，cloud-login/JWT 不变。
- 菜谱：种子 upsert 可回退旧 60 数据版本，但不做删除式回滚；推荐器按 recipe-ready 数据运行。
- 天气：清空 QWeather 配置后仅使用已有 stale/neutral，不会暗中调用其他供应商。
- AI：关闭功能开关即可，后端可选字段保持兼容。
- 任何线上异常先回滚 Cloud Run 版本和小程序体验版，不修改生产数据以“救火”。
