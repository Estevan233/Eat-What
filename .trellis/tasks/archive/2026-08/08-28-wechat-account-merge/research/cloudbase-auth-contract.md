# CloudBase 正式身份、游客 JWT 与 HTTP Repository 契约

调研日期：2026-08-28

## 1. 结论摘要

1. 项目当前正式登录不是“昵称头像授权”，而是 `wx.cloud.callContainer -> 平台身份 Header -> openid -> 业务 JWT`。头像昵称只是可跳过的公开资料。
2. CloudBase 文档确实描述了 SDK 调用时平台自动携带 `X-WX-OPENID`、`X-WX-APPID`、`X-WX-ENV` 等信息，但是否可在本项目实际部署形态中安全信任，取决于请求是否只能从受信 CloudBase 入口到达。应用仅比较 Header 值，挡不住公网攻击者自己填写同名 Header。
3. 合并源的授权必须是签名和有效期通过的游客 JWT，并进一步查询数据库确认 `sub` 对应 active/已绑定同目标的 guest。`guest_id` 只能用于游客登录时定位高熵访客标识，不能直接授权合并。
4. 当前 CloudBase MySQL HTTP Repository 只封装单次 GET/POST/PATCH/DELETE。官方 MySQL HTTP API 文档描述的也是单请求 CRUD、upsert 和返回偏好；当前代码没有跨表事务接口。因此 REST 合并必须按可重放状态机设计，不能假定 SQLAlchemy 的 transaction 能照搬。
5. 合并后让源 `users` 留作 `merged` tombstone，普通鉴权查询数据库状态并拒绝，是使旧游客 JWT 立即失效且阻止 guestId 重生的最小可靠方案。

## 2. CloudBase 身份 Header 的官方契约

### 2.1 官方 AnyService 使用指南

CloudBase 官方 AnyService 使用指南写明，通过 SDK 调用服务时系统会自动在 HTTP Header 中携带小程序与环境信息，包括：

| Header | 官方含义 |
|---|---|
| `X-WX-OPENID` | 小程序用户 openid |
| `X-WX-APPID` | 小程序 AppID |
| `X-WX-UNIONID` | 满足条件时的小程序 unionid |
| `X-WX-FROM-OPENID/APPID/UNIONID` | 环境/资源复用场景的原始调用方身份 |
| `X-WX-ENV` | 当前云开发环境 ID |
| `X-WX-SOURCE` / `X-WX-PLATFORM` | 调用来源和平台 |
| `X-Cloudbase-Request-Id`（响应） | 请求追踪 ID |

来源：<https://docs.cloudbase.net/anyservice/usage>

### 2.2 官方 Cloud Run 小程序访问指南

官方指南要求小程序先初始化云环境，再用 `wx.cloud.callContainer` 和 `X-WX-SERVICE` 调云托管；默认只能访问已关联环境，跨环境需显式开启环境共享。文档还说明：

- callContainer 是授权小程序/公众号到服务的链路；
- 后端可在适用的微信云托管形态直接获得 openid；
- 若服务只给小程序/公众号调用，建议关闭公网访问并使用 callContainer。

来源：<https://docs.cloudbase.net/run/develop/access/mini>

### 2.3 官方集成函数示例

CloudBase 集成中心文档对小程序调用 HTTP 云函数的描述更直接：平台自动注入 `x-wx-openid/x-wx-appid`，不需要用户再做一套显式登录或在客户端传 Token 来证明微信身份。

来源：<https://docs.cloudbase.net/integration/usage>

### 2.4 对本项目的约束

本项目代码 `backend/app/core/cloud_context.py` 当前执行：读取 `X-WX-OPENID/X-WX-APPID/X-WX-ENV`，要求 appid/env 等于配置。这个检查能约束“身份属于哪个 App/环境”，但它本身不能证明 Header 来源。

因此上线前必须验证：

1. 实际部署属于哪一种 CloudBase/微信云托管入口，Header 是否由平台实测注入；官方文档不同产品页的能力边界不能混用。
2. cloud-login 是否可从公网直接访问。若可以，攻击者能够自行提交 `X-WX-OPENID`；AppID/env 多半不是秘密，值相等不代表请求可信。
3. 若使用环境共享，后端究竟应读取 `X-WX-*` 还是 `X-WX-FROM-*` 必须在真实环境确认。本任务默认不启用跨应用自动并号。
4. `openid` 只从受信 Header 读取，绝不从 body/query 读取。

推论：PRD 中“可信微信 OpenID”是一个**部署入口 + Header 校验**的联合前提，不是“看见三个 Header 就信”。若公网入口无法隔离，合并功能必须保持关闭。

## 3. 本地认证实现事实

### 3.1 JWT

`backend/app/core/security.py` 当前使用 HS256（配置可指定，但生产校验只允许 HS256），payload 只有：

- `sub`：内部 user id 字符串；
- `iat`：签发时间；
- `exp`：过期时间；
- 默认 TTL 七天，校验允许 5 秒时钟偏差。

`decode_token` 使用配置中的固定算法列表并验证签名/过期；`get_current_user` 再用 `sub` 查 `users`。这正好提供合并源验证需要的两层：JWT 证明“持有服务器签发的会话”，数据库行证明“这个 subject 当前是什么账户、是否仍 active”。

JWT 标准把 `sub` 定义为 subject、`exp` 为到期时间、`iat` 为签发时间，并要求应用自行定义哪些 claims 必需及如何处理。JWT 安全最佳实践要求验证算法和应用上下文，不能只做 base64 解码。

来源：

- <https://datatracker.ietf.org/doc/html/rfc7519>
- <https://datatracker.ietf.org/doc/html/rfc8725>

### 3.2 游客身份

`backend/app/services/user_service.py` 当前把 `guest_id` 拼为唯一 `openid=guest:<guest_id>`；`miniapp/src/stores/user.ts` 在本地生成并保存 guestId。`guest-login` 只凭 guestId 创建/复用用户并签 JWT。

这意味着 guestId 本质上也是一个高熵 bearer secret，而不是经过第三方实名的身份。合并接口若再直接收 guestId，没有增加任何校验层；要求游客 JWT 至少带来：

- 服务器签名；
- 有效期；
- 固定算法校验；
- `sub` 到数据库 guest 行的绑定；
- 合并状态和目标绑定的服务端判定。

残余风险必须诚实记录：知道 guestId 的人目前仍可先调用 guest-login 获取游客 JWT。因此 guestId 必须保持高熵、不得记录日志或暴露 URL；本任务解决的是“合并不能只信原始 ID”，不是把匿名游客凭空升级成强实名账户。

## 4. 为什么旧游客 JWT 不能只靠前端删除

`miniapp/src/stores/user.ts` 当前微信登录成功后删除本地 guestId，但旧 JWT 在服务端仍可能有效七天。只清 storage 有三个问题：

1. 其他设备副本、调试器或泄露 token 仍可继续访问源游客数据。
2. 合并若删掉源行但 guest-login 仍按同一 guestId 创建，游客身份会“复活”。
3. CloudBase HTTP 部分成功时，客户端可能先丢凭证，服务端却还没迁完。

研究结论：在 `users` 保存 `account_status` 和 `merged_into_user_id`，普通鉴权每次查库拒绝 merging/merged；保留源行占住 `guest:<guest_id>` 唯一键。旧 JWT 可在合并专用端点被有限识别，只用于恢复已绑定同目标的操作，不允许读业务数据。

## 5. CloudBase MySQL HTTP API 契约

官方 MySQL HTTP API 的基础路径是：

```text
https://{envId}.api.tcloudbasegateway.com/v1/rdb/rest/{table}
```

使用 Bearer AccessToken/API key，并通过 `Prefer` 控制：

- `return=representation`：写后返回行；
- `count=exact`：读取精确计数；
- `resolution=merge-duplicates` / `ignore-duplicates`：upsert 冲突处理；
- POST/PATCH/DELETE 的 `Content-Range` 可表达受影响行数。

来源：<https://docs.cloudbase.net/http-api/mysqldb/mysql-restful-api>

本地 `backend/app/repositories/cloudbase_rdb.py` 与该契约吻合：

- GET 可对 503/传输故障有限重试；
- 写操作 `retryable=False`，不会盲重试非幂等写；
- update/delete 强制至少一个 filter；
- 返回行和 affected 从响应解析。

本地 `CloudBaseRepository` 当前把写操作包装成单模型 insert/upsert/update/delete；没有 transaction/begin/commit/rollback。官方页面也只给出了单 HTTP 请求的数据操作契约，未给当前 Python Repository 提供跨表事务能力。

因此可确认的是：**本项目现有 HTTP Repository 不能提供跨五张表原子性**。不能进一步武断宣称 CloudBase MySQL 本身没有事务；MySQL 当然有事务，只是这条已实现的 HTTP Repository 契约没有暴露它。设计应基于实际可调用能力，而不是平台宣传页上“完整 SQL”四个字自我催眠。

## 6. REST 合并的可靠性推论

### 6.1 不能在客户端/HTTP 层盲重试写

网络错误可能发生在服务端提交之后、客户端收到响应之前。对 insert 立即原样重试会制造唯一键冲突或重复；对更新/删除若没有稳定过滤，会误改其他行。

合并步骤必须：

- source 先持久化 `merging + target`；
- 每条变更用稳定主键 + 旧 owner 过滤；
- 写失败返回可重试错误；
- 下一次请求先重读，已完成即跳过，未完成才继续；
- 0 行/409 后重读目标唯一键，判断“已经收敛”还是“真实冲突”。

### 6.2 不宜依赖泛化 upsert

`resolution=merge-duplicates` 的冲突目标由数据库唯一键决定，而本任务每张表有不同“正式优先、游客补缺”规则。直接 upsert 会把游客字段覆盖正式字段，尤其 profile、daily 和 dining，业务语义不可接受。

所以只在创建正式 `users(openid)` 的并发唯一键竞争中允许“写后重读”；五类数据均使用显式冲突解析。

### 6.3 分页

当前 repository 的 `list(..., limit=None)` 不能作为“返回全部”的永久保证。合并应按主键升序分页/批次处理，并在末尾查询 source 残留；否则一个历史较长的游客会被默认分页悄悄截断，表面成功、实际丢半截，堪称数据工程版的掩耳盗铃。

## 7. 数据冲突的底层原则

- **唯一集合**（favorites）：集合并集，正式重复行保留。
- **追加事实**（recommendation_events）：保留事件 identity 和快照，只迁 ownership；不重新生成 request id。
- **按日投影**（daily_logs）：正式行是当日主投影；推荐/选择快照必须按一致性组整体选择，不能字段拼接。
- **用户记忆**（dining_memories）：正式 verdict 是明确决策，游客只补空 note。
- **健康档案**（user_profiles）：正式完整提交优先；仅真正 `NULL` 的可选字段补游客。空 forbidden list 是有效选择，不是缺失。
- **公开资料**（nickname/avatar）：微信身份与资料分离；占位昵称/空头像可补，但不影响认证结果。

## 8. 已识别风险与验证项

| 风险 | 后果 | 控制/验证 |
|---|---|---|
| 公网可伪造 `X-WX-*` | 任意指定 openid 登录/夺取合并目标 | 入口隔离、关闭公网、真实 callContainer 验收；不满足则开关关闭 |
| guestId 泄露 | 攻击者可先获取游客 JWT | 高熵、本地存储、不进日志/URL；合并仍必须 JWT |
| REST 中途成功后断网 | 部分表已迁移 | merging 状态、稳定过滤、重读重放、最终残留校验 |
| 同一源并发合并到不同目标 | 数据错绑 | 首次目标持久绑定，不同目标 409 |
| 唯一键冲突被 upsert 覆盖 | 正式数据被游客覆盖 | 每表显式规则，不泛化 upsert |
| 合并后旧 token 仍有效 | 继续访问源账户 | 普通 guard 查 account_status；source tombstone |
| 合并后 guestId 重生 | 新游客分叉或正式权限泄露 | tombstone 占唯一 openid；guest-login 明确拒绝 |
| 客户端先清游客状态 | 失败后无法重试 | 成功响应后才原子切换，失败保留 |
| 本地缓存仍是游客视图 | 展示覆盖正式优先结果 | 成功后清用户级缓存并重拉 |
| `profile_complete` 被误当认证 | 跳过资料就像“未登录” | UserRead 增加 account_kind，isGuest 不看资料字段 |

## 9. 本地证据路径

- 正式登录/Header 校验：`backend/app/api/v1/auth.py`、`backend/app/core/cloud_context.py`
- JWT：`backend/app/core/security.py`、`backend/app/core/deps.py`
- 游客身份：`backend/app/services/user_service.py`、`backend/app/schemas/auth.py`
- HTTP Repository：`backend/app/repositories/cloudbase_repository.py`、`backend/app/repositories/cloudbase_rdb.py`
- 五类模型：`backend/app/models/{favorite,daily_log,recommendation_event,dining_memory,user_profile}.py`
- 现有 REST 失败语义测试：`backend/tests/test_cloudbase_rdb.py`、`backend/tests/test_cloudbase_repository.py`、`backend/tests/test_cloudbase_rest_services.py`
- 小程序 token/guestId 生命周期：`miniapp/src/stores/user.ts`、`miniapp/src/auth/storage.ts`、`miniapp/src/api/request.ts`
- 资料完善与身份分离：`miniapp/src/auth/profile-onboarding.ts`、`backend/app/schemas/auth.py`

## 10. 最终决策

- 合并入口复用 `/auth/cloud-login`，目标来自受信 CloudBase Header，源来自当前 Bearer 游客 JWT。
- 不新增 guestId/source user id 合并参数。
- `users` 增加账户类型、状态和目标绑定；源游客永久 tombstone。
- SQLAlchemy 使用状态封禁 + 事务迁移；CloudBase HTTP 使用同一规则的可重放状态机。
- 正式资料优先，只有文档明确的缺失状态允许游客补齐。
- 正式 JWT 只在五类数据收敛和源残留校验通过后返回。
- 昵称头像可跳过；`account_kind` 才是前端游客/正式身份判断依据。
