# 微信正式身份与游客数据合并 PRD

## 1. 问题

当前小程序的游客与微信用户分别落在 `users` 表：游客用 `openid=guest:<guest_id>`，微信正式用户用 CloudBase 私有链路注入的 OpenID。`miniapp/src/stores/user.ts` 在微信登录成功后直接删除本地 `guest_id`，没有迁移游客数据，导致收藏、每日记录、推荐曝光、外食记忆和健康档案留在旧用户下。

更危险的是，`guest_id` 只是客户端生成并保存的高熵标识，不是已验证身份。合并若只接收一个 `guest_id`，等于把“知道一个字符串”当成“拥有这个账户”；这种门禁水平，和在门口贴一张“闲人免进”差不多。

## 2. 目标

1. 用户从当前游客会话发起微信登录时，系统同时验证 CloudBase 注入的正式微信身份与当前游客 JWT，再把游客数据归入正式用户。
2. 同一游客到同一微信用户的合并可安全重试；网络中断、响应丢失或 CloudBase HTTP Repository 部分成功时，不重复数据、不改绑到其他正式用户。
3. 合并完成后，旧游客 JWT 不能继续访问业务接口，旧 `guest_id` 也不能换取正式用户权限。
4. SQLAlchemy 与 CloudBase HTTP Repository 两条数据路径具有同一业务结果和冲突规则。
5. 昵称、头像允许用户跳过完善；资料是否完整不参与身份认证判断。

## 3. 身份定义与信任边界

- **正式身份**：请求经已授权的 CloudBase `wx.cloud.callContainer` 私有入口到达，后端校验平台注入的 `X-WX-OPENID`、`X-WX-APPID`、`X-WX-ENV` 后得到的微信主体。客户端自填同名 Header 不构成正式身份。
- **游客合并凭证**：签名、算法、有效期均通过校验，且 `sub` 能解析到一个 `account_kind=guest` 用户的当前游客 JWT。合并接口不接受 `guest_id`、`source_user_id` 作为合并授权依据。
- **公开资料**：昵称、头像及 `profile_complete` 只用于展示和可跳过的资料完善引导，不证明微信身份，也不决定 JWT 是否可签发。
- **正式用户优先**：正式用户已有且语义完整的数据不被游客数据覆盖；仅按第 5 节定义的“缺失”规则用游客数据补齐。

## 4. 范围

### 4.1 本任务包含

- 微信 `cloud-login` 与游客 JWT 的安全绑定和合并。
- `users` 的身份类型、合并状态、目标绑定与时间记录。
- 合并 `favorites`、`daily_logs`、`recommendation_events`、`dining_memories`、`user_profiles`。
- 正式用户公开昵称/头像的“正式优先、游客补缺”。
- SQLAlchemy 事务路径与 CloudBase HTTP Repository 可重放状态机路径。
- 小程序登录状态、缓存切换、失败重试和可跳过资料完善。
- 数据库迁移、自动化测试、灰度启用、停用和回滚方案。

### 4.2 非目标

- 不合并两个不同微信 OpenID 的正式账户。
- 不把 `unionid` 用作跨应用自动并号依据。
- 不实现用户自助“撤销合并”或自动拆分已经合并的数据。
- 不要求用户必须上传头像或填写昵称后才能登录。
- 不启动任务、不部署 Cloud Run、不修改生产 CloudBase 配置。

## 5. 数据合并规则

| 数据 | 无冲突 | 正式用户已有冲突记录 | 幂等唯一键 |
|---|---|---|---|
| `favorites` | 将游客记录归到正式用户 | 保留正式记录，删除游客重复记录 | `(user_id, food_id)` |
| `recommendation_events` | 保留原 `id/request_id/created_at`，只改 `user_id` | `request_id` 是全局唯一；若发现异常冲突则停止并报警，不静默覆盖 | `request_id` |
| `daily_logs` | 保留原行和时间，只改 `user_id` | 保留正式行；推荐快照组或选择快照组仅在正式组整体缺失时由游客组补齐，随后删除游客重复行 | `(user_id, log_date)` |
| `dining_memories` | 保留原行，只改 `user_id` | 正式 `shop/dish/verdict/created_at` 优先；仅当正式 `note` 为空时补游客 `note`，随后删除游客重复行 | `(user_id, normalized_shop_name, normalized_dish_name)` |
| `user_profiles` | 正式用户无档案时，将游客档案改属正式用户 | `birthday/gender/forbidden_tags` 以正式档案为准；`height_cm/weight_kg/constitution_type/constitution_scores` 仅在正式值为 `NULL` 时补游客值 | `user_id` 主键 |
| `users.nickname/avatar_url` | 不改变正式微信标识 | 正式非占位昵称和非空头像优先；正式昵称为 `微信用户`/`用户` 且游客昵称不是 `游客`/占位值时可补昵称，正式头像为空时可补游客头像 | 正式 `openid` |

`daily_logs` 的“组”定义如下，避免把两次不同推荐拼成一只三头六臂的记录：

- 推荐快照组：`recommendation_event_id`、`recommended_food_ids_json`、`recommended_meal_json`。
- 选择快照组：`chosen_food_ids_json`、`chosen_meal_json`、`chosen_total_nutrition_json`。
- 正式组中任一字段已有有效内容时，整组以正式记录为准；只有整组均为 `NULL`/空集合时才复制游客组。
- `mood`、`activity_level`、`weather_tag`、`dining_mode`、`audience`、`party_size` 等标量在正式行存在时始终以正式行为准；默认值也是有效业务值，不是假装成空白的后门。

## 6. 功能需求

### R1. 正式身份校验

后端必须先验证 CloudBase 私有入口提供的 OpenID、AppID 和环境 ID，再创建或读取正式用户。生产入口若允许公网直接伪造 `X-WX-*` Header，则不得启用账户合并。

### R2. 游客所有权校验

合并只使用请求 `Authorization` 中的游客 JWT。JWT 必须通过签名、算法、`exp/iat` 和 `sub` 校验，并解析到游客用户；请求体中的 `guest_id`、用户 ID、昵称或头像均不能替代该校验。

### R3. 合并绑定与状态机

游客用户采用 `active -> merging -> merged` 单向状态。首次合并把目标正式用户写入游客用户的 `merged_into_user_id`；后续重试只允许同一目标。不同正式 OpenID 试图接管已绑定游客时，系统必须返回冲突且不迁移数据。

### R4. 重试与部分失败

所有表迁移步骤必须以稳定主键和所有者过滤执行，并可从任意已完成步骤后重放。CloudBase HTTP 写入不做盲目自动重试；遇到“服务端可能已写入但响应丢失”时，下一次请求通过重读数据库状态收敛。

### R5. 旧游客权限失效

普通鉴权依赖必须拒绝 `merging` 和 `merged` 游客。合并专用校验器可在同一目标上有限接受旧游客 JWT 以恢复/确认同一合并，但该凭证不得访问收藏、档案、推荐、历史或外食接口。已合并的 `guest_id` 再次游客登录时不得映射到正式用户或创建同名新游客。

### R6. 正式登录与资料完善分离

可信微信 OpenID 验证成功后，即使昵称仍为默认值、头像为空或用户跳过资料完善，系统也必须签发正式 JWT。前端的 `isGuest` 必须由服务端返回的账户类型判断，不能再由本地 `guest_id` 或 `profile_complete` 猜测。

### R7. 客户端切换原子性

小程序在微信登录请求成功前保留游客 JWT、`guest_id` 和游客缓存，以便重试；成功拿到正式 JWT 后才原子替换会话、清理 `guest_id` 和旧的用户级缓存，并按正式用户重新读取档案。失败时不得提前把唯一恢复凭证扔进垃圾桶。

### R8. 可观测性与隐私

结构化日志记录合并阶段、源/目标内部用户 ID、迁移计数、结果、耗时和 CloudBase request id；不得记录 JWT、Authorization、guest_id、openid、unionid、完整健康档案或完整请求体。

### R9. 兼容与发布

数据库变更必须是可先行部署的加法迁移；旧客户端不带游客 JWT 时仍可完成普通微信登录。合并功能必须有服务端开关，迁移、后端、客户端按顺序灰度发布。

## 7. 验收标准（EARS）

- [ ] **AC1** 当请求经受信 CloudBase 私有入口携带有效微信身份，且 `Authorization` 是一个有效、未合并的游客 JWT 时，系统应把该游客绑定到该正式用户并合并第 5 节的全部五类数据。
- [ ] **AC2** 当微信登录请求没有游客 JWT 时，系统应执行普通正式登录，不创建合并任务，也不要求昵称或头像。
- [ ] **AC3** 当请求只提供 `guest_id`/游客用户 ID 而没有游客 JWT 时，系统应忽略这些原始源标识、不得读取或修改游客数据，并仅按 AC2 处理普通正式登录；当请求携带了无效、过期、`sub` 非法、用户不存在或非游客的 Bearer JWT 时，系统应返回 401 且不得执行合并。
- [ ] **AC4** 当相同游客 JWT 与相同微信 OpenID 因超时或响应丢失重复提交时，系统应返回同一个正式用户，最终每个业务唯一键最多一条记录，迁移计数不得随重试虚增。
- [ ] **AC5** 当 CloudBase HTTP Repository 在任一迁移步骤后失败时，系统应返回可重试错误、保持目标绑定不变，并在后续同目标重试时从数据库现状继续直至 `merged`。
- [ ] **AC6** 当已绑定游客被另一个微信 OpenID 发起合并时，系统应返回 `409 MERGE_TARGET_CONFLICT`，不得改写原目标或泄露游客数据。
- [ ] **AC7** 当正式用户与游客收藏同一道菜时，系统应只保留正式用户下一条收藏；当仅游客收藏时，系统应保留其原创建时间并迁入正式用户。
- [ ] **AC8** 当正式用户与游客同日均有 `daily_logs` 时，系统应按第 5 节的两个快照组执行正式优先、游客补缺，且不得产生 `(user_id, log_date)` 冲突或悬空 `recommendation_event_id`。
- [ ] **AC9** 当游客存在推荐曝光记录时，系统应保留每条事件的 `id`、`request_id`、快照和时间，仅把所有权改为正式用户；若发现全局 `request_id` 异常冲突，系统应停止合并并报告一致性错误。
- [ ] **AC10** 当正式用户已有同一店铺菜品记忆时，系统应保留正式 verdict，仅在正式 note 为空时补游客 note；无冲突记忆应完整迁移。
- [ ] **AC11** 当正式用户已有健康档案时，系统应按第 5 节字段规则保留正式资料并仅补 `NULL`；正式 `forbidden_tags=[]` 应视为有效选择而不是缺失。
- [ ] **AC12** 当正式微信身份没有头像、昵称仍为默认值或用户选择“先跳过”时，系统应保持正式登录态；资料完善状态不得把用户降级成游客或阻止业务 JWT。
- [ ] **AC13** 当合并进入 `merging` 或 `merged` 后，旧游客 JWT 调用任一普通受保护接口时，系统应返回 401；同一 `guest_id` 再次游客登录时应拒绝恢复或访问正式账户。
- [ ] **AC14** 当合并最终成功时，系统应在全部数据校验通过后才签发/返回正式 JWT；小程序应随后清理游客标识和陈旧缓存，并以服务端 `account_kind=wechat` 判断正式身份。
- [ ] **AC15** 当同一冲突夹具分别运行在 SQLAlchemy 与 CloudBase HTTP Repository 测试替身上时，系统应产生等价的目标用户数据、源用户状态和错误码。
- [ ] **AC16** 当日志记录合并成功、冲突、重试或失败时，日志应包含阶段与内部用户 ID，但不得包含 JWT、guest_id、openid、unionid 或健康档案正文。

## 8. 发布完成定义

- Alembic MySQL 离线编译、SQLite 测试建表和迁移回归通过。
- 后端单元、API、双 Repository 合并契约、并发/重试/旧 Token 回归全部通过。
- 前端 Vitest、类型检查、Lint 和 mp-weixin 构建通过。
- 微信开发者工具完成“游客产生五类数据 -> 微信登录 -> 数据仍可见 -> 旧 Token 401 -> 重试无重复”的实链路验收。
- 生产启用前确认目标 CloudBase 环境/AppID、`callContainer` 身份 Header 实测值及公网入口关闭策略；没有这一步，就只能叫“本地方案”，不能硬着头皮自封“安全上线”。
