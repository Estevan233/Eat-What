# “今天吃啥”完整餐食、轻菜谱与 CloudBase 全栈设计

- 日期：2026-08-12
- 状态：已确认，等待书面规格复核
- 唯一开发仓库：`/root/miniapp-trellis`
- 当前开发分支：`feat/recommendation-diversity`
- 小程序 AppID：`wx59c5620b7a894f8e`
- CloudBase 环境：`cloud1-d8gz4jm8vb964a1c9`
- 云托管服务名：`eat-what-api`

## 1. 目标

MVP 的核心任务是让用户在 30 秒内决定“今天吃什么”，并且点击推荐结果后能够真正完成做饭。首页一次给出：

1. 一套完整餐食，由主菜、蔬菜和主食三个餐位组成；
2. 整餐估算热量、蛋白质和预计烹饪时间；
3. 两个单菜替换项；
4. 每道菜可进入应用内轻菜谱；
5. 用户可以收藏单菜并保存当天实际选择，后续推荐读取历史以减少重复。

系统必须同时在 H5 本地开发、微信开发者工具模拟器、二维码预览和真机调试中工作。微信端不得请求 `localhost`，生产数据不得存放在云托管实例磁盘。

## 2. 范围

### 2.1 本期交付

- A“餐盘清单式”首页结果布局；
- 一套主推荐完整餐食和两个单菜替换项；
- 60 道精选、可执行的轻菜谱；
- 每份估算能量、蛋白质、脂肪和碳水化合物；
- 现有 204 道菜品数据继续保留；
- 推荐多样性、近七日去重和天气降权；
- 微信登录、游客登录、档案、体质、收藏、选择和历史完整贯通；
- FastAPI 容器化部署到 CloudBase 云托管；
- CloudBase MySQL 持久化与 Alembic 迁移；
- 微信开发者工具和至少一次真机预览验收；
- 规则推荐器保留未来 Agent 有界重排接口。

### 2.2 明确不在本期

- 根据冰箱现有食材推荐的用户界面和接口实现；
- 外卖平台接入、门店搜索、价格比较和下单；
- Agent 在线生成菜谱或营养数值；
- 60 张独立菜品摄影图；
- 医疗诊断、治疗建议或精确减脂处方；
- 多套生产环境和复杂灰度发布。

“现有食材推荐”和“外卖/Agent”只保留数据与接口边界，不显示灰色入口或“敬请期待”按钮。

## 3. 仓库与文件位置

### 3.1 唯一事实来源

所有源码修改、依赖安装、测试和构建均在 WSL 仓库 `/root/miniapp-trellis` 中执行。

| 位置 | 角色 | 规则 |
| --- | --- | --- |
| `/root/miniapp-trellis` | 唯一开发仓库 | 允许修改、测试、构建和提交 |
| `\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis` | Windows 对同一 WSL 仓库的访问路径 | 仅供微信开发者工具读取构建产物 |
| `C:\Users\Estevan\Documents\devlop\Eat-What` | 独立 Windows 克隆 | 本期只读，不同步、不覆盖、不删除 |
| `https://github.com/Estevan233/Eat-What.git` | 远端交付仓库 | 仅从 WSL 仓库推送已验证提交 |

`miniapp/dist` 是生成目录，不直接编辑。微信开发者工具日常导入：

```text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\dev\mp-weixin
```

发布前生产构建目录：

```text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\build\mp-weixin
```

## 4. 运行架构

### 4.1 本地开发

```text
H5 / Vitest
  → HttpTransport（uni.request）
  → http://127.0.0.1:8000
  → FastAPI
  → 本地 SQLite
```

本地 SQLite 只用于快速开发、后端测试和 H5 联调，不作为云端数据源。

### 4.2 微信模拟器、预览和真机

```text
mp-weixin
  → wx.cloud.init(cloud1-d8gz4jm8vb964a1c9)
  → CloudTransport（wx.cloud.callContainer）
  → X-WX-SERVICE: eat-what-api
  → FastAPI 云托管
  → CloudBase MySQL
```

微信端不配置 API Base URL，也不通过 `wx.request` 访问本地或公网 API。`callContainer` 负责私有链路访问，因此不需要小程序业务域名。

### 4.3 云托管

- 后端目录提供 `Dockerfile` 和 `.dockerignore`；
- Uvicorn 监听 `0.0.0.0` 和平台提供的 `PORT`；
- `/health` 用于部署和烟测；
- MVP 资源从 0.25 vCPU、0.5 GB、最小实例 0、最大实例 1 开始；
- 联调完成后关闭公网访问，只允许小程序私有链路；
- 日志写标准输出，记录 CloudBase request ID，不记录 token、openid 全值或秘密；
- 开启预算告警并观察冷启动、内存和数据库 CCU 后再调整资源。

## 5. 前端组件边界

### 5.1 Request 内核

业务 API 只依赖统一 `request()`，底层按平台选择传输：

- `HttpTransport`：H5、本地测试使用 `uni.request`；
- `CloudTransport`：`MP-WEIXIN` 使用 `wx.cloud.callContainer`；
- `ResponseNormalizer`：统一解析 `statusCode`、字符串 JSON、`{ok, code, message, data}` 和 CloudBase request ID；
- `AuthPolicy`：附加 Bearer JWT，401 时只触发一次清理和登录跳转；
- `CaseMapper`：请求 camelCase 转 snake_case，响应反向转换；
- `LoadingManager`：使用引用计数，避免并发请求互相提前隐藏 loading；
- `ErrorMapper`：把平台错误转成稳定 `ApiError` code。

默认超时为 10 秒。推荐接口可设 15 秒以容忍冷启动。非幂等 POST 不自动重试，避免重复写推荐事件或选择记录。

### 5.2 页面与状态

- `pages/today/today.vue`：上下文输入、主餐、替换项、缓存和异常态；
- `components/MealPlateCard.vue`：完整餐食、总营养、餐位列表和“就吃这套”；
- `components/MealSubstitution.vue`：替换单个餐位并重新计算总营养；
- `pages/recipe/recipe.vue`：单菜轻菜谱详情；
- `stores/daily.ts`：推荐快照、替换后的当前餐、选择、上次成功缓存；
- `stores/favorite.ts`：收藏单菜；
- `pages/history/history.vue`：显示实际选择的整餐快照；
- `pages/favorite/favorite.vue`：显示收藏菜品并进入菜谱详情。

页面不得直接调用 `uni.request` 或 `wx.cloud.callContainer`。

## 6. 后端组件边界

- API 路由：只做鉴权、输入校验和调用服务；
- 推荐评分器：输出安全候选及分项分数；
- 组餐器：按餐位和营养兼容性组成完整餐食；
- 菜谱服务：读取结构化 Recipe 并返回稳定详情；
- 收藏与日志服务：处理持久化和幂等约束；
- Repository：隔离 SQLModel 查询，业务服务不依赖 SQLite/MySQL 方言细节；
- Cloud Context Middleware：读取并校验 `X-WX-OPENID`、`X-WX-APPID`、`X-WX-ENV` 和 request ID；
- Agent Reranker：未来扩展点，本期实现仍为规则引擎。

## 7. 鉴权与秘密管理

### 7.1 微信登录主路径

微信端调用 `POST /api/v1/auth/cloud-login`。FastAPI 从 CloudBase 私有链路注入的请求头取得 openid，并验证：

- `X-WX-APPID` 必须等于配置的 AppID；
- `X-WX-ENV` 必须等于配置的 CloudBase 环境；
- `X-WX-OPENID` 必须存在；
- 生产环境必须关闭公网访问。

验证通过后，后端按 openid 创建或读取用户，并签发项目现有 JWT。业务接口继续校验 JWT，因此不会把平台传输方式扩散到业务层。

### 7.2 兼容路径

现有 `wx.login → code2session` 端点保留为受控兼容路径，但不作为小程序主路径。`WX_SECRET` 不再是云端服务启动的无条件必填项；只有显式启用兼容端点时才要求配置。

### 7.3 游客登录

游客 ID 在设备本地生成，后端创建游客用户并签发同款 JWT。游客可以保存档案、收藏和历史。清除小程序数据后游客身份不可恢复，界面需明确提示。

### 7.4 秘密

此前公开过的 AppSecret 必须在微信后台轮换。新 AppSecret、`JWT_SECRET`、数据库密码和连接串只存放于本地 `.env` 或 CloudBase 环境变量；不得进入 Git、构建产物、日志、截图或规格文档。

## 8. 数据模型

### 8.1 Food

保留现有字段和 204 条数据，新增：

- `meal_role`：`main | vegetable | staple`；汤仍由 `category` 和 `cooking_method` 表达，可根据主要食材归入主菜或蔬菜餐位；
- `recipe_ready`：是否可进入本期推荐输出；
- 可选的 `visual_key`：无照片时使用确定性的角色图标和渐变视觉。

只有 `recipe_ready=true` 的菜品可以出现在主餐和替换项中。本期该集合固定为经过校验的 60 道菜，其中至少包含 20 道主菜、20 道蔬菜和 10 道主食；剩余名额按菜谱质量和多样性分配。

### 8.2 Recipe

Recipe 与 Food 一对一，包含：

- `food_id` 唯一外键；
- `servings`；
- `ingredients_json`：规范化名称、数量、单位和“适量”标记；
- `steps_json`：4–6 个有序步骤；
- `prep_time_min`、`cook_time_min`；
- `nutrition_per_serving_json`：`energy_kcal`、`protein_g`、`fat_g`、`carb_g`，可选 `fiber_g` 和 `sodium_mg`；
- `difficulty`：本期只使用 `easy | normal`；
- `source_name`、`source_url`：均可空；
- `nutrition_basis`、营养计算来源和 `version`；
- 创建和更新时间。

食材量允许家庭烹饪表达，例如“香菜 1 小把”“盐适量”，但影响营养计算的主食材、肉类和食用油必须给出克或毫升数量。

### 8.3 DailyLog

保留旧 `recommended_food_ids_json` 和 `chosen_food_ids_json` 以兼容现有代码，新增：

- `recommendation_event_id`；
- `recommended_meal_json`：当时主餐和两个替换项的快照；
- `chosen_meal_json`：用户替换后实际选择的完整餐快照；
- `chosen_total_nutrition_json`。

保存快照而不是只在展示时反查 Recipe，避免菜谱版本更新后历史记录发生变化。

### 8.4 RecommendationEvent

保留曝光事件，新增：

- 主餐 food IDs；
- 两个替换项 food IDs 及对应餐位；
- 评分器版本、组餐器版本和可选 Agent 名称；
- 推荐快照摘要。

不记录精确坐标或用户完整身体数据。

### 8.5 迁移与种子

- 引入 Alembic，停止依赖 `create_all` 进行生产模式升级；
- 生产部署在接流量前执行 `alembic upgrade head`；
- 食物和菜谱种子使用稳定键幂等 upsert；
- 禁止现有“先清 foods 表再导入”的逻辑用于生产；
- 数据校验脚本必须阻止少于 60 道 recipe-ready、步骤数不为 4–6、缺少每份能量或餐位不足的构建。

## 9. 推荐与组餐

### 9.1 硬过滤

评分前必须移除：

- 用户忌口命中的菜；
- 体质明确禁忌的菜；
- `recipe_ready=false` 的菜；
- 数据缺失或营养数值非法的菜。

硬过滤不允许被 Agent、天气或其他分数覆盖。

### 9.2 规则评分 v3

总基础分为 75：

| 维度 | 满分 |
| --- | ---: |
| 营养与整餐互补 | 20 |
| 体质适配 | 12 |
| 心情 | 10 |
| 活动量 | 8 |
| 做法多样性与耗时 | 13 |
| 天气 | 6 |
| 节气 | 5 |
| 星座彩蛋 | 1 |

天气由原 `15/75` 降为 `6/75`。星座不进入推荐理由的主要句子，仅可作为趣味彩蛋。

近七日选择和曝光继续单独施加新鲜度惩罚。当天存在足够未曝光候选时，不再次展示当天已曝光菜品。

### 9.3 完整餐食

组餐器执行以下流程：

1. 选择最高质量的主菜候选；
2. 选择与主菜不同类别和做法的蔬菜；
3. 选择主食；
4. 校验三个餐位无重复、均有菜谱且不触犯硬过滤；
5. 汇总每份营养；
6. 预计总时间使用 `所有菜 prep_time 之和 + 最大 cook_time`，表达为可并行处理下的粗略用时并标记“约”；
7. 生成两个单菜替换项，优先分别替换主菜和蔬菜；
8. 替换后总能量不得偏离原整餐超过 25%，除非无安全候选，此时可以扩大到 35% 并在理由中说明更清淡或更丰盛；
9. 标准档案返回两个替换项。若用户的忌口或体质硬过滤导致安全候选不足，可返回 0–1 个并明确提示，绝不为了凑数放宽安全约束。

推荐响应结构：

```text
recommendationId
primaryMeal
  items[main, vegetable, staple]
  totalNutrition
  estimatedTimeMin
  reason
substitutions[2]
context
engine
```

### 9.4 用户选择

`POST /api/v1/daily/choose` 接收：

- `recommendation_id`；
- 三个 `selected_food_ids`；
- 当前替换信息。

后端验证选择来自该推荐事件且每个餐位只有一个菜，再幂等保存。重复提交返回同一结果，不产生重复选择事件。

### 9.5 Agent 扩展边界

未来 Agent 只接收已经通过硬过滤的候选和有限上下文，返回 food ID、`[-10,+10]` 调整值和短理由。后端必须校验：

- food ID 属于候选集；
- 无重复；
- 分数调整有界；
- 超时、异常或非法输出立即回退规则引擎；
- Agent 不能生成营养值、修改硬过滤或直接写数据库。

## 10. 轻菜谱与营养表达

- 首页显示“约 N kcal/份”，不再把每 100 克数值误写成单份热量；
- 详情页同时显示每份营养，必要时补充原 Food 的 `kcal/100g`；
- 整餐营养等于当前三个餐位每份营养之和；
- 数值根据食材重量、用油量、份数和可靠食物成分资料计算：先汇总配方中各食材营养，再除以 `servings` 得到每份值；无法量化的“盐适量”等不伪造精确数值，并在营养依据中说明；
- 所有营养数值标记为估算，不使用“精准”“治疗”“保证减脂”等措辞；
- 外部来源链接是补充入口，不影响应用内完成主任务；
- 任意第三方热链图片或无法控制的 WebView 页面不得成为关键流程依赖。

无 `image_url` 时，界面使用统一的餐位图标、品牌橙和低饱和渐变占位。图片存在时懒加载，加载失败回退占位，不展示破图。

## 11. 错误处理与降级

| 场景 | 行为 |
| --- | --- |
| 天气获取失败或用户拒绝位置 | 使用 `mild/any`，隐藏具体天气理由，推荐继续 |
| 云托管冷启动或超时 | 显示“服务正在启动，请重试”，保留上次成功推荐为只读 |
| 401 | 只清 JWT，不清游客 ID；全局只触发一次登录跳转 |
| 档案不存在 | 引导完善档案，不发送必然失败的推荐请求 |
| MySQL 不可用 | 返回 503；不伪造保存成功、不离线排队写入 |
| 菜谱异常缺失 | 正常情况下由 `recipe_ready` 阻止；若数据异常则回退基础菜品信息 |
| Agent 异常 | 记录降级原因并回退规则推荐 |
| CloudBase 服务名或环境错误 | 显示“服务配置错误”，同时记录 request ID 供排查 |
| 网络离线 | 展示缓存推荐和明确的离线标记，禁用会产生写入的成功反馈 |

## 12. 接口

本期新增或调整：

- `POST /api/v1/auth/cloud-login`：CloudBase 请求头登录；
- `POST /api/v1/auth/guest-login`：保留；
- `POST /api/v1/auth/wx-login`：兼容路径；
- `POST /api/v1/daily/recommend`：返回完整餐、两个替换项和事件 ID；
- `POST /api/v1/daily/choose`：保存整餐选择；
- `GET /api/v1/daily/today`：返回当天整餐快照；
- `GET /api/v1/daily/history`：返回整餐历史；
- `GET /api/v1/food/{food_id}/recipe`：轻菜谱详情；
- 现有收藏接口保持单菜收藏语义；
- `GET /health`：返回服务和数据库连接状态摘要，不返回秘密。

OpenAPI 是前后端契约来源。新增类型优先从 OpenAPI 生成或由契约测试校验，避免前后端各手写一套后悄悄分叉。

## 13. 配置

### 13.1 小程序构建变量

- `VITE_CLOUDBASE_ENV_ID=cloud1-d8gz4jm8vb964a1c9`
- `VITE_CLOUDBASE_SERVICE=eat-what-api`
- H5 可继续使用 `VITE_API_BASE_URL=http://127.0.0.1:8000`

不得把 AppSecret 或数据库凭证打入 Vite 变量。

### 13.2 后端环境变量

- `ENVIRONMENT`
- `DEBUG`
- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_TTL_MINUTES`
- `WX_APPID`
- `CLOUDBASE_ENV_ID`
- `WX_SECRET`，仅兼容路径启用时需要
- `ENABLE_CODE2SESSION=false`，生产默认关闭兼容登录端点
- `OPEN_METEO_API`
- `PORT`

## 14. 测试策略

### 14.1 后端

- 评分分项和天气降权单元测试；
- 忌口和体质硬过滤测试；
- 组餐餐位、无重复、营养求和和替换偏差测试；
- 近七日曝光与选择多样性测试；
- Recipe 数据质量和 seed 幂等测试；
- Cloud Header 登录、错误 AppID/环境和缺失 openid 测试；
- guest-login、JWT、档案、收藏、选择和历史 API 测试；
- SQLite 测试套件与 MySQL 迁移烟测；
- Docker `/health` 烟测。

### 14.2 前端

- HttpTransport 和 CloudTransport 响应归一化测试；
- CloudBase 字符串 JSON、非 2xx、网络失败和 request ID 测试；
- 401 单次跳转和游客 ID 保留测试；
- Meal substitution 与总营养重算测试；
- 推荐缓存和 stale 状态测试；
- `lint:check`、`type-check`、Vitest；
- H5 和 mp-weixin 双构建。

### 14.3 真实链路

在 CloudBase 云托管部署后依次执行：

1. `/health`；
2. 通过开发者工具的 `callContainer` 执行微信登录；
3. 游客登录；
4. 建档和体质信息；
5. 推荐完整餐；
6. 打开三道菜菜谱；
7. 替换一道菜并保存整餐；
8. 收藏和取消收藏；
9. 查看当天和历史；
10. 关闭并重启小程序确认数据仍存在；
11. 拒绝定位、弱网和冷启动降级；
12. 微信开发者工具模拟器、二维码预览和真机调试各执行至少一次。

## 15. 构建与部署

### 15.1 小程序

开发：

```bash
cd /root/miniapp-trellis/miniapp
npm run dev:mp-weixin
```

发布前：

```bash
npm run lint:check
npm run type-check
npm test
npm run build:mp-weixin
```

微信开发者工具导入对应 `dist/dev/mp-weixin` 或 `dist/build/mp-weixin`，不得导入 `miniapp` 源码根目录。

### 15.2 后端

部署前必须通过：

```bash
ruff check .
mypy app
pytest
docker build
docker run + /health smoke
alembic upgrade head
```

通过用户本人完成的 `tcb login` 或 CloudBase 控制台授权部署，不在聊天中传递云账号密码。部署目标：

```text
environment: cloud1-d8gz4jm8vb964a1c9
service: eat-what-api
port: 8080
```

## 16. 完成标准

只有以下条件全部满足才可称为完成：

- 微信开发者工具不再出现 `app.json is not found`；
- 模拟器和手机网络面板均无 `localhost:8000`；
- 微信登录和游客登录均能进入首页；
- 主餐固定三个餐位；标准测试档案固定返回两个替换项，极端忌口档案允许少于两个且必须说明原因；
- 60 道菜谱均有 4–6 步、食材量和每份估算营养；
- 当前 204 条食物数据仍在且生产 seed 不清表；
- 天气权重测试证明降至 `6/75`，天气失败仍可推荐；
- 忌口硬过滤在所有推荐路径生效；
- 连续重选和近七日历史满足多样性规则；
- 选择、收藏和历史在容器重启后仍存在；
- 冷启动、弱网、拒绝定位和数据异常均有可理解提示；
- 后端测试、前端测试、静态检查、双端构建和 Docker 烟测全部通过；
- CloudBase 烟测、微信模拟器和至少一次真机预览通过；
- Git 提交只来自 WSL 唯一仓库，Windows 独立克隆未被修改。

## 17. 实施顺序

1. 记录并保护当前 dirty worktree，运行基线测试；
2. 实现双 Transport、CloudBase 初始化和 Cloud Header 登录；
3. 加入 Docker、Alembic、CloudBase MySQL 和云端健康检查；
4. 增加 Recipe 与整餐快照模型，导入并校验 60 道菜谱；
5. 实现推荐 v3、组餐和两个替换项；
6. 实现 A 首页、菜谱详情、收藏和历史界面；
7. 完成自动化、容器、云端、模拟器和真机验收；
8. 分阶段提交并从 WSL 推送到 GitHub。

## 18. 参考资料

- CloudBase 微信小程序访问云托管：<https://docs.cloudbase.net/run/develop/access/mini>
- CloudBase 云托管服务开发要求：<https://docs.cloudbase.net/run/develop/developing-guide>
- CloudBase 临时存储：<https://docs.cloudbase.net/run/deploy/configuring/storage/local>
- CloudBase 源码部署：<https://docs.cloudbase.net/run/deploy/deploy/deploying-source-code>
- CloudBase MySQL：<https://docs.cloudbase.net/database/configuration/db/tdsql/initialization>
- uni-app CLI：<https://uniapp.dcloud.net.cn/worktile/CLI.html>
- 中国居民平衡膳食餐盘：<https://dg.cnsoc.org/article/04/ya2PbmF0S_CNY0z_Vd9HGQ.html>
- 国家卫健委餐饮食品营养标识指南：<https://www.nhc.gov.cn/wjw/c100175/202012/681df34f0e8f485fb33e8a659e30f6da/files/1-1%E9%A4%90%E9%A5%AE%E9%A3%9F%E5%93%81%E8%90%A5%E5%85%BB%E6%A0%87%E8%AF%86%E6%8C%87%E5%8D%97%20%20%E6%8C%87%E5%8D%97%E6%AD%A3%E6%96%87.pdf>
