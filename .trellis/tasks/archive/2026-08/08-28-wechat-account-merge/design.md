# 微信正式身份与游客数据合并技术设计

## 1. 现状与设计结论

现有正式登录链路是：

```text
miniapp cloudLogin()
  -> request.ts 自动附带当前业务 JWT
  -> wx.cloud.callContainer
  -> CloudBase 注入 X-WX-OPENID / X-WX-APPID / X-WX-ENV
  -> POST /api/v1/auth/cloud-login
  -> users(openid) upsert
  -> 后端签发业务 JWT
```

现有游客链路则是：

```text
guest_id（客户端高熵标识）
  -> POST /api/v1/auth/guest-login
  -> users(openid="guest:<guest_id>")
  -> 后端签发游客 JWT
```

设计采用同一个 `/auth/cloud-login` 作为“普通正式登录/游客升级”的入口。请求中的 CloudBase Header 证明目标正式身份，`Authorization` 中的游客 JWT 证明源游客身份。接口不新增 `guest_id` 或 `source_user_id` 合并参数，避免把可猜/可抄的标识错当授权。

## 2. 总体架构

```text
                                  ┌─ 无 Authorization ───────────┐
wx.cloud.callContainer ──────────>│                              ├─ 普通微信登录
  平台注入可信微信 Header           │  POST /auth/cloud-login       │
  客户端保留当前 Bearer JWT         │                              ├─ 同正式身份重登
                                  └─ 有 Authorization ───────────┤
                                                                 └─ 游客 JWT -> 合并状态机
                                                                            │
                                                      ┌─────────────────────┴─────────────────────┐
                                                      │                                           │
                                               SQLAlchemy                                  CloudBase HTTP Repository
                                        状态封禁 + 事务迁移                         状态封禁 + 可重放逐步迁移
                                                      │                                           │
                                                      └──────────── 同一冲突规则/最终快照 ──────────┘
```

认证、合并、资料完善分成三条独立判断：

1. CloudBase 可信身份决定“是不是正式微信用户”。
2. 游客 JWT 决定“有没有权迁移这个游客的数据”。
3. 昵称/头像决定“是否展示资料完善引导”，不参与前两项。

## 3. 数据模型与迁移

新增 Alembic 版本：`backend/alembic/versions/20260828_07_account_merge_state.py`，`down_revision="20260820_06"`。

### 3.1 `users` 加法字段

| 字段 | 类型/默认 | 作用 |
|---|---|---|
| `account_kind` | `VARCHAR(16) NOT NULL DEFAULT 'wechat'` | `guest` / `wechat`，服务端身份事实 |
| `account_status` | `VARCHAR(16) NOT NULL DEFAULT 'active'` | `active` / `merging` / `merged` |
| `merged_into_user_id` | nullable FK -> `users.id` | 游客一旦开始合并即绑定唯一正式目标 |
| `merge_started_at` | nullable datetime | 状态机审计与卡住任务排查 |
| `merged_at` | nullable datetime | 合并完成时间 |

迁移按以下顺序执行：

1. 以安全默认值添加列；先不改变旧代码读写。
2. `UPDATE users SET account_kind='guest' WHERE openid LIKE 'guest:%'`，其余保持 `wechat`。
3. 创建 `ix_users_account_kind_status(account_kind, account_status)` 和 `ix_users_merged_into_user_id`。
4. 添加自引用外键。SQLite 测试使用 batch alter；MySQL 离线 SQL 必须编译通过。

不删除源游客 `users` 行。它作为永久 tombstone 保留 `guest:<guest_id>` 唯一键和目标绑定，从而同时做到：旧 JWT 的 `sub` 仍可被识别并拒绝、同一 `guest_id` 不会重新创建游客、游客凭证不能直接换成正式账户权限。

### 3.2 模型约束

- `account_kind=wechat` 的用户只能保持 `account_status=active`，不得设置 `merged_into_user_id`。
- `account_kind=guest` 可从 `active` 单向进入 `merging`，再进入 `merged`。
- `merging/merged` 必须有 `merged_into_user_id`，且目标不能等于自身。
- 应用层强制上述状态机；迁移不依赖 MySQL 特有 ENUM，保证 SQLite/MySQL 兼容。

## 4. API 契约

### 4.1 `POST /api/v1/auth/cloud-login`

请求体保持 `{}`；不传游客 ID。请求 Header：

- CloudBase 平台注入：`X-WX-OPENID`、`X-WX-APPID`、`X-WX-ENV`，可选 `X-WX-UNIONID`、request id。
- 客户端请求层自动附带：`Authorization: Bearer <当前业务 JWT>`（若存在）。

分支：

| 当前 Bearer | 处理 |
|---|---|
| 无 | 普通正式登录 |
| 对应同一正式用户 | 幂等重登 |
| 对应其他正式用户 | `409 SESSION_IDENTITY_CONFLICT`，不静默切号 |
| 有效 active 游客 | 绑定并执行合并 |
| 同目标的 merging/merged 游客 | 恢复或确认同一合并 |
| 无效/过期/不存在/类型不符 | 401，不降级成“忽略 Token 后普通登录” |
| 已绑定到其他正式用户的游客 | `409 MERGE_TARGET_CONFLICT` |

成功响应在现有 `LoginResponse` 上做加法扩展：

```json
{
  "token": "formal-jwt",
  "user": {
    "id": 42,
    "nickname": "微信用户",
    "avatar_url": null,
    "profile_complete": false,
    "account_kind": "wechat"
  },
  "merge_status": "not_requested | completed"
}
```

不向客户端返回源游客 ID、目标绑定、迁移计数或内部阶段。它们只用于服务端结构化日志。

### 4.2 `POST /api/v1/auth/guest-login`

保留现有兼容接口。读取到 `active` 游客时可签发游客 JWT；读取到 `merging/merged` tombstone 时返回 `409 GUEST_ACCOUNT_UPGRADED`，绝不返回目标正式用户，也不重新创建同 `guest_id` 用户。

### 4.3 普通受保护接口

`get_current_user` 在 JWT 校验和 `sub` 查用户后，必须要求 `account_status=active`。`merging/merged` 统一返回 401。数据库行是最终事实；即使未来 JWT 增加 `account_kind` claim，也不能只信 claim。

合并入口使用独立的 `resolve_merge_credential()`：它复用相同 JWT 签名/时间校验，但只允许恢复“已绑定到当前可信正式目标”的 `merging/merged` 游客。这个窄口存在是为了处理“服务端成功、客户端没收到响应”的重试，不赋予任何普通数据访问权。

## 5. 合并状态机

```text
active guest
   │ 校验 guest JWT + trusted target
   ▼
merging (target 固定，普通接口立即拒绝旧游客 JWT)
   │
   ├─ 任一步失败 -> 保持 merging，返回可重试 503
   │                   │
   │                   └─ 同 target + 同 guest JWT 重放
   │
   ├─ 不同 target -> 409，状态不变
   │
   └─ 五类数据迁移 + 源数据归零校验
       ▼
merged (返回正式 JWT)
```

第一次状态变更必须在迁移前持久化，让随后到达的普通请求不再用旧游客身份写业务数据。迁移完成前不返回正式 JWT。状态机无自动逆向；`merged` 不回到 `active`。

## 6. 统一合并算法

服务入口：`account_merge_service.merge_guest_into_wechat(session, source, target)`，返回内部 `MergeSummary`。所有步骤按稳定主键升序、固定批次读取；每次 mutation 同时带记录主键和当前 `source_user_id` 过滤，避免重试误改已经转移或被并发处理的行。

### 6.1 前置与目标公开资料

1. 读取/创建正式 `target`，明确 `account_kind=wechat`。
2. 校验源为 guest，源目标绑定为空或等于 target。
3. 把源置为 `merging` 并固定 `merged_into_user_id`。
4. 正式 `nickname` 不是占位值时保留；仅占位值可由游客非占位昵称补齐。正式 `avatar_url` 非空时保留，否则可补游客头像。绝不复制游客 openid/unionid。

### 6.2 `user_profiles`

- 目标无 profile：把游客 profile 的 `user_id` 更新为目标 ID。
- 两边都有：保留目标 `birthday/gender/forbidden_tags`；目标 `height_cm/weight_kg/constitution_type/constitution_scores` 为 `NULL` 时复制游客值；更新目标后删除游客 profile。
- 目标 `forbidden_tags=[]` 是明确的空集合，不从游客覆盖。

### 6.3 `recommendation_events`

- 逐批更新游客事件 `user_id=target.id`，保留事件主键、`request_id`、快照和时间。
- 在迁移 `daily_logs` 前完成，因为日报可能引用这些事件。
- 若同一个事件主键或 request id 指向不可解释的目标外记录，抛 `MERGE_DATA_CONFLICT`，不得生成新事件或篡改 request id。

### 6.4 `daily_logs`

- 按 `log_date` 查目标冲突。
- 无冲突：更新游客行所有者。
- 有冲突：按 PRD 的推荐快照组/选择快照组整体合并；正式标量始终保留；更新正式行后删除游客行。
- 复制游客 `recommendation_event_id` 前验证该事件已属于目标，防止悬空或跨用户引用。

### 6.5 `favorites`

- 目标没有同 food 收藏：按原主键把游客记录的 `user_id` 改为目标。
- 目标已有：保留目标记录并删除游客重复记录。
- 不重新插入收藏，因此原 `created_at` 在无冲突时得以保留。

### 6.6 `dining_memories`

- 目标没有相同规范化店铺+菜品：更新游客记录所有者。
- 目标已有：保留目标展示名、verdict、created_at/updated_at；仅目标 note 为 `NULL` 或去空白后为空时复制游客 note，然后删除游客重复记录。

### 6.7 收尾校验

再次查询五类表，要求不存在 `user_id=source.id` 的记录；检查目标唯一键没有重复，日报引用的推荐事件均属于目标。通过后把源置为 `merged`、写 `merged_at`，再签发正式 JWT。

如果收尾时仍发现源记录，返回 `503 MERGE_IN_PROGRESS` 而不是假装成功。对于在 `merging` 标记前已经通过鉴权的并发请求，最终归零扫描是必要兜底；CloudBase HTTP 无跨请求锁，因此发布时还要用并发故障测试验证该窗口。

## 7. 双 Repository 实现

### 7.1 SQLAlchemy

- 首次 `active -> merging` 单独提交，尽早封禁旧游客身份。
- 迁移阶段使用显式事务；MySQL 对源/目标用户和冲突行按稳定顺序 `SELECT ... FOR UPDATE`，降低并发死锁。
- 所有冲突解析、行迁移、源归零校验和 `merged` 状态在同一事务完成；异常 rollback 后源仍为 `merging`，可重试。
- SQLite 测试不假装支持生产级行锁，只验证状态和最终数据；并发锁语义用 MySQL/Repository 契约测试覆盖。

### 7.2 CloudBase HTTP Repository

当前 `CloudBaseRepository` 只有单请求 CRUD，底层写请求明确不自动重试；设计不假设一个不存在的跨表事务。

- 增加 `update_many(record, filters) -> list[ModelT]`（或等价返回受影响行的方法），允许条件写在并发重放时返回 0 行而不是把它误判成 500。
- 每次写以主键+旧 owner 过滤；写失败后不在同一调用里盲重试。
- 下一次 cloud-login 重读 source/target 和各表，已经完成的行自然消失，未完成的继续处理。
- 唯一键冲突通过“先读取目标、再移动或删除源”解析；若并发后写返回 0/409，则重读该唯一键，满足预期即视为已收敛，否则报冲突。
- 逐表分页/按 ID 批次处理，不能依赖 HTTP API 的隐含默认分页上限。

两条路径共用纯函数冲突策略（profile 字段合并、daily 两组快照、公开资料占位判断），防止 SQLAlchemy 和 REST 各写一套“差不多”的规则，最后差得恰好够制造线上幽灵数据。

## 8. 小程序状态切换

### 8.1 身份状态

- `UserRead` 增加 `accountKind: 'guest' | 'wechat'`。
- `isGuest = profile?.accountKind === 'guest'`；`guestId` 只用于游客重登录，不能再作为身份事实。
- `profileComplete` 只控制资料完善引导。正式用户跳过后仍是 `wechat`。

### 8.2 登录/重试顺序

1. 当前游客 token 有效：直接 `cloudLogin()`，请求层自动附带它。
2. 有 `guestId` 但 token 为空（例如过期后被 401 清除）：先 `guestLogin(guestId)` 取得新的游客 JWT，再调用 `cloudLogin()`。
3. cloud-login 成功前不删除 guestId、不清游客 token/缓存。
4. 成功后写入正式 token/UserRead，再清 guestId、`userProfile`、`constitution` 等旧缓存并重新拉取正式目标数据。
5. 503/网络错误保留原会话，用户重试同一流程。
6. `GUEST_ACCOUNT_UPGRADED` 表示服务端已完成但本地状态异常；客户端不得用 guestId 取正式权限，应重新走可信 cloud-login。

存储写入采用单一 helper 顺序完成，避免 `clearAuthStorage()` 的订阅回调先把刚写入的正式 token 清掉。

## 9. 错误与日志

| 错误码 | HTTP | 场景 | 可重试 |
|---|---:|---|---|
| `CLOUD_IDENTITY_INVALID` | 401 | 可信 Header 缺失/环境或 AppID 不符 | 修复入口后 |
| `AUTH_ERROR` / `GUEST_MERGE_TOKEN_INVALID` | 401 | 游客 JWT 无效、过期、类型不符 | 重新游客登录后 |
| `SESSION_IDENTITY_CONFLICT` | 409 | 当前正式 JWT 与 Header 正式用户不同 | 清理陈旧会话后 |
| `MERGE_TARGET_CONFLICT` | 409 | 游客已绑定其他正式用户 | 否 |
| `GUEST_ACCOUNT_UPGRADED` | 409 | 用已合并 guestId 重新游客登录 | 改走 cloud-login |
| `MERGE_DATA_CONFLICT` | 409 | 数据唯一键/引用关系异常 | 人工处理 |
| `MERGE_IN_PROGRESS` | 503 | REST 部分失败或源数据尚未归零 | 是，同目标重试 |

日志事件建议：`account_merge_started`、`account_merge_step`、`account_merge_resumed`、`account_merge_completed`、`account_merge_conflict`。字段只含 source/target 内部 ID、step、counts、duration、request id、backend；禁止 token、guest_id、openid、unionid 和档案内容。

## 10. CloudBase 入口安全前提

应用代码只能校验 Header 值与配置相符，无法仅凭同名 Header 证明它确实由平台注入。上线闸门必须：

1. 在真实目标环境用 `wx.cloud.callContainer` 记录脱敏后的 Header 是否存在及含义。
2. 确认小程序与环境的关联/共享配置符合预期。
3. 若服务只给小程序使用，关闭公网访问；若必须保留公网业务 API，则把 cloud-login 放到仅平台可达入口或增加可验证的网关来源机制，不能让公网请求直达该路由并自填 `X-WX-*`。
4. AppID/env 只能作为约束，不是来源证明；openid 更不能由客户端 body 传入。

## 11. 发布与回滚

### 11.1 发布顺序

1. 备份生产数据库并记录待合并游客数量；运行加法迁移和 backfill。
2. 部署理解新字段、但 `ENABLE_GUEST_ACCOUNT_MERGE=false` 的后端；确认普通游客/微信登录兼容。
3. 验证 CloudBase 私有 Header、公网入口和双 Repository 实环境烟测。
4. 发布能保留/附带游客 JWT 的小程序版本。
5. 小流量开启合并，观察 `merging` 停留时长、503/409、源残留数和唯一键冲突。

### 11.2 回滚边界

- **尚无合并发生**：关闭开关，回滚小程序/Cloud Run 版本；保留加法列，不急着 downgrade。
- **已有 `merging/merged`**：立即关闭新合并，但必须保留新鉴权 guard 和 tombstone 逻辑。直接回滚到旧后端会让旧游客 JWT 复活，属于安全事故，不叫回滚。
- **单个合并卡住**：保持 source=`merging`，从日志定位阶段后同目标重试或运行受审计的修复脚本；不得手工把状态改回 active 后继续写。
- **数据级撤销**：本任务不自动拆分。生产启用前必须有数据库备份；已合并数据若需恢复，从备份在隔离库重建并人工审计，不在在线库反向猜所有权。
- **迁移 downgrade**：只有确认不存在 `merging/merged` 行且应用已回滚后才允许删除新列和索引。

## 12. 关键权衡

- 保留源游客 tombstone 会多留一行 `users`，代价极小，却能阻止 guestId 重生并使旧 token 可明确拒绝；物理删除看着干净，安全语义反而更脏。
- SQLAlchemy 可以加强事务一致性，CloudBase HTTP Repository 不能假装拥有相同事务边界，因此以持久状态机和幂等步骤定义共同语义。
- 正式档案优先不等于“正式所有空值都神圣不可碰”。规则只在能区分真正缺失时补值；`forbidden_tags=[]`、`neutral` 等合法默认/选择不会被游客旧数据偷梁换柱。
