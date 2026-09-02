# 微信正式身份与游客数据合并实施计划

> 当前任务仍处于 `planning`。以下清单只定义实施顺序、验证和回滚点；在用户审阅并明确批准、随后执行 `task.py start` 前，不改生产代码、不迁移数据库、不部署。

实施采用 TDD：先写失败测试和冲突夹具，再写最小实现；每阶段同时验证 SQLAlchemy 与 CloudBase HTTP Repository，禁止等写完一整套后才发现另一条路径根本没上车。

## 0. 基线与上线前置（AC1、AC15、AC16）

- [ ] 记录后端/小程序当前全量测试、类型检查、Lint、构建和 MySQL Alembic 离线编译结果。
- [ ] 在真实测试环境确认 `wx.cloud.callContainer` 注入的 OpenID/AppID/env Header 形状，确认目标服务公网入口策略；若 Header 可由公网直达请求伪造，则保持 `ENABLE_GUEST_ACCOUNT_MERGE=false`。
- [ ] 准备一套固定冲突夹具：源/目标各含 profile、重复/不重复 favorite、同日/异日 daily log、事件、重复/不重复 dining memory，用于两种 Repository 逐字段比较。
- [ ] 确认生产备份/回档能力、当前 migration head、`guest:%` 用户数量和已有异常外键/唯一键；只统计数量，不导出 openid/guest_id 到普通日志。

验证：

```bash
cd backend
pytest tests/ -q
ruff check app/ tests/
mypy app/
python -m alembic upgrade head --sql

cd ../miniapp
npm test
npm run type-check
npm run lint:check
npm run build:mp-weixin
```

回滚点：本阶段只读；发现入口不可信或数据已有冲突时停止，不写迁移。

## 1. 数据模型与加法迁移（AC4、AC6、AC13、AC15）

### 1.1 先写失败测试

- [ ] 扩展 `backend/tests/test_mysql_migrations.py`：断言新列、索引、自引用外键和 guest backfill SQL 可为 MySQL 编译。
- [ ] 新增/扩展模型测试：SQLite `create_all` 后 `User` 可表达 `guest/wechat` 与 `active/merging/merged`，非法状态由服务层拒绝。
- [ ] 为旧 schema 数据构造迁移场景：`guest:%` 回填为 guest，其余回填为 wechat，所有旧用户初始 active。

### 1.2 实现

- [ ] 新增 `backend/alembic/versions/20260828_07_account_merge_state.py`：添加 `account_kind`、`account_status`、`merged_into_user_id`、`merge_started_at`、`merged_at`，完成 backfill、索引和 FK。
- [ ] 修改 `backend/app/models/user.py`：增加对应字段和精确 Literal/字符串类型；不删除/改名现有列。
- [ ] 修改 `backend/app/core/config.py` 与 `backend/.env.example`：增加默认关闭的 `enable_guest_account_merge` / `ENABLE_GUEST_ACCOUNT_MERGE`。
- [ ] 若模型聚合因新类型需要导出，最小调整 `backend/app/models/__init__.py`；不新增无关表。

验证：

```bash
cd backend
pytest tests/test_mysql_migrations.py -q
python -m alembic upgrade head --sql
pytest tests/test_db_config.py tests/test_cloudbase_repository.py -q
```

回滚点：开关仍关闭。加法字段可保留；只有确认没有 `merging/merged` 行时才执行 downgrade。

## 2. 认证状态与 API 契约（AC1、AC2、AC3、AC6、AC12、AC13、AC14）

### 2.1 先写失败测试

- [ ] 新增 `backend/tests/test_api_v1/test_account_merge.py` 的身份矩阵：无 token 普通登录、同正式用户重登、其他正式 token 冲突、有效游客 token 进入合并、无效/过期/错误 `sub`/非游客 token 无任何写入。
- [ ] 扩展 `backend/tests/test_api_v1/test_cloud_login.py`：默认昵称+空头像仍签正式 JWT，响应明确 `account_kind=wechat`，`profile_complete=false` 仅是 UI 状态。
- [ ] 扩展 `backend/tests/test_api_v1/test_guest_login.py`：游客响应 `account_kind=guest`；`merging/merged` guestId 返回 `GUEST_ACCOUNT_UPGRADED`，不返回目标用户。
- [ ] 扩展 `backend/tests/test_security.py` 或新增 `backend/tests/test_auth_dependencies.py`：普通 guard 拒绝 merging/merged 源；合并专用 resolver 只允许同目标恢复。

### 2.2 实现

- [ ] 修改 `backend/app/schemas/auth.py`：`AuthUserRead` 增加 `account_kind`；`LoginResponse` 增加 `merge_status`，保持原字段兼容。
- [ ] 修改 `backend/app/core/cloud_context.py`：继续校验 OpenID/AppID/env，可读取平台可选 unionid；禁止从 body 读身份。
- [ ] 修改 `backend/app/core/security.py`：复用统一 JWT 签名/时间校验；不得为合并增加“只 decode 不验签”的捷径。
- [ ] 修改 `backend/app/core/deps.py`：普通用户必须 active；新增可复用的 optional bearer/合并凭证解析边界，返回数据库中的源用户而非信任 token claim 的账户类型。
- [ ] 修改 `backend/app/core/errors.py`：集中定义 `SESSION_IDENTITY_CONFLICT`、`MERGE_TARGET_CONFLICT`、`GUEST_ACCOUNT_UPGRADED`、`MERGE_DATA_CONFLICT`、`MERGE_IN_PROGRESS`，状态码按 design.md。
- [ ] 修改 `backend/app/services/user_service.py`：创建用户时写 account kind；游客 tombstone 不再走普通 upsert；正式用户并发 upsert 遇唯一键竞争时重读收敛。
- [ ] 修改 `backend/app/api/v1/auth.py`：`cloud-login` 先验证可信目标，再按 Bearer 类型调用普通登录/合并；没有完成五类数据前不签正式 JWT。

验证：

```bash
cd backend
pytest tests/test_security.py tests/test_api_v1/test_auth.py \
  tests/test_api_v1/test_cloud_login.py tests/test_api_v1/test_guest_login.py \
  tests/test_api_v1/test_account_merge.py -q
```

回滚点：开关关闭时 `cloud-login` 维持普通登录；新 guard/tombstone 逻辑即使回滚功能也必须保留。

## 3. 纯冲突策略与 SQLAlchemy 合并（AC4、AC7–AC11、AC13–AC15）

### 3.1 先写失败测试

- [ ] 新增 `backend/tests/services/test_account_merge_service.py`，逐项覆盖：
  - favorite 取并集、重复保留正式行、原时间保留；
  - recommendation event 只换 owner，主键/request id/快照/时间不变；
  - daily 无冲突迁移、同日两个快照组正式优先且仅整组缺失时游客补齐；
  - daily 引用事件已改属目标，无悬空/跨用户引用；
  - dining 冲突保留正式 verdict，仅补空 note；
  - profile 无目标时整体迁移，有目标时只补允许的 NULL，`forbidden_tags=[]` 不覆盖；
  - 正式 nickname/avatar 占位补齐与非占位保留；
  - 二次执行结果完全一致，源五表归零，源用户 tombstone 保留。
- [ ] API 集成测试保存旧游客 token，合并后用它访问 profile/favorite/daily/dining 均为 401。
- [ ] 两个不同目标并发/顺序请求同一源，第二个得到 409，源绑定不变。

### 3.2 实现

- [ ] 新增 `backend/app/services/account_merge_service.py`：定义 `MergeSummary`、纯字段/快照冲突函数、统一步骤顺序和 SQLAlchemy 分支。
- [ ] 首次绑定先提交 source=`merging`；迁移用显式 transaction 和稳定锁顺序，异常 rollback 后允许同目标恢复。
- [ ] 严格以记录主键+source owner 过滤 mutation；不得用批量“把 user_id 全改掉”撞唯一键后再碰运气。
- [ ] 事件先于日报迁移；每步完成后做源残留与引用一致性检查；最后才写 `merged` 并返回正式身份。
- [ ] 增加结构化合并日志，字段遵循 design.md 的敏感信息禁区。

验证：

```bash
cd backend
pytest tests/services/test_account_merge_service.py \
  tests/test_api_v1/test_account_merge.py -q
pytest tests/test_api_v1/test_profile.py tests/test_api_v1/test_favorite.py \
  tests/test_api_v1/test_daily.py tests/test_api_v1/test_dining.py -q
```

回滚点：失败源保持 merging，不回退 active；修复后同目标重试。不得在在线库手工改 owner 绕过唯一键策略。

## 4. CloudBase HTTP Repository 可重放实现（AC4、AC5、AC7–AC11、AC15）

### 4.1 先写失败测试

- [ ] 扩展 `backend/tests/test_cloudbase_repository.py`：条件更新 0/1/N 行能被调用方区分，JSON/时间序列化与主键省略保持正确。
- [ ] 新增 `backend/tests/test_account_merge_cloudbase_rest.py`（或在 `test_cloudbase_rest_services.py` 中建独立 describe 区）：同一冲突夹具与 SQLAlchemy 的归一化快照完全相等。
- [ ] 在内存 REST double 注入“第 N 次写成功后丢响应”“503 未写入”“并发唯一键 409”，逐个阶段重试并断言最终无重复、绑定不变、计数稳定。
- [ ] 覆盖超过单页批次的数据，证明不会因 HTTP 默认分页上限漏迁。

### 4.2 实现

- [ ] 修改 `backend/app/repositories/cloudbase_repository.py`：增加安全的条件多行更新/返回受影响行能力；保留现有 `update()` 的严格单行语义。
- [ ] 仅当新契约确实需要底层返回信息时修改 `backend/app/repositories/cloudbase_rdb.py`；写操作仍不做盲目自动重试，API key 不进异常文本。
- [ ] 在 `backend/app/services/account_merge_service.py` 实现 REST 分支：按 ID 分页、读取目标唯一键、移动或删源；0 行/409 后重读判断是否已收敛。
- [ ] 任一步不可确认时保持 source=`merging` 并抛 `MERGE_IN_PROGRESS`；不得提前返回正式 JWT。

验证：

```bash
cd backend
pytest tests/test_cloudbase_repository.py tests/test_cloudbase_rdb.py \
  tests/test_cloudbase_rest_services.py tests/test_account_merge_cloudbase_rest.py -q
pytest tests/test_cloudbase_error_mapping.py -q
```

回滚点：关闭合并开关；保留 REST repository 的加法 API 和新 guard。卡住记录按同目标重试，不删除 tombstone。

## 5. 小程序会话提升与缓存（AC2、AC4、AC5、AC12–AC14）

### 5.1 先写失败测试

- [ ] 扩展 `miniapp/src/api/auth.test.ts`：`cloudLogin` 不发送 guestId/source ID，仍通过统一 request 让当前 Bearer 自动附带。
- [ ] 扩展 `miniapp/src/auth/storage.test.ts`：正式登录成功时“替换 token/profile -> 清 guestId/用户级缓存”的顺序正确；通知监听不会清掉新 token。
- [ ] 扩展 `miniapp/src/stores/user.test.ts`：
  - `isGuest` 由 `accountKind` 而非 guestId/profileComplete 决定；
  - 有有效游客 token 时直接升级；
  - 有 guestId 但 token 为空时先 guest re-login，再 cloud-login；
  - 503/网络失败保留游客 token、guestId、profile/userProfile/constitution；
  - 成功后替换正式会话、清陈旧缓存、`accountKind=wechat`；
  - 默认昵称/空头像/跳过资料仍是正式身份。
- [ ] 扩展 `miniapp/src/auth/profile-onboarding.test.ts` 与 `miniapp/src/pages/auth` 相关测试：资料完善只对正式且不完整用户提示，可跳过，不参与登录成功判断。
- [ ] 扩展 `miniapp/src/api/request.test.ts`：401 仍保留 guestId 以便重新签游客 JWT；普通 503 不清认证存储。

### 5.2 实现

- [ ] 修改 `miniapp/src/types/api.ts`：`UserRead.accountKind`、`LoginResponse.mergeStatus`，保持 snake/camel 转换契约。
- [ ] 修改 `miniapp/src/auth/profile-onboarding.ts`：兼容旧缓存缺少 accountKind 的归一化；不从 profileComplete 推导身份。
- [ ] 修改 `miniapp/src/auth/storage.ts`：提供单一的会话提升 helper，成功后才清 guestId 和用户级缓存，避免 `clearAuthStorage` 回调误清新会话。
- [ ] 修改 `miniapp/src/stores/user.ts`：微信登录前按需恢复游客 JWT；成功后原子切换；`isGuest` 读取服务端账户类型。
- [ ] 修改 `miniapp/src/pages/auth/auth.vue`：保留 loading 防重；503 提示可重试；资料完善可跳过；不索取头像昵称作为登录前置。
- [ ] `miniapp/src/api/auth.ts` 保持 cloud-login body 不含 guest 标识；只按新增响应字段更新类型/注释。

验证：

```bash
cd miniapp
npm test -- src/api/auth.test.ts src/api/request.test.ts \
  src/auth/storage.test.ts src/auth/profile-onboarding.test.ts \
  src/stores/user.test.ts
npm run type-check
npm run lint:check
npm run build:mp-weixin
```

回滚点：客户端发布前失败可直接回旧版本；客户端发布后若后端开关关闭，普通 cloud-login 仍可用，但不会声称游客数据已合并。

## 6. 全量验证、实环境验收与灰度（AC1–AC16）

- [ ] 后端全量：pytest、Ruff、mypy、Alembic MySQL 离线 SQL；确认现有推荐幂等、profile、favorite、daily、dining 回归不变。
- [ ] 前端全量：Vitest、vue-tsc、ESLint、H5/mp-weixin 构建。
- [ ] Docker/Cloud Run 测试环境：SQLAlchemy（若可用直连）和 `cloudbase_rest` 至少各跑一轮固定冲突夹具或等价烟测。
- [ ] 微信开发者工具：游客创建五类数据，微信登录，核对正式用户可见；保留旧游客 token 的调试请求返回 401；重复点击/断网重试不重复。
- [ ] 故障演练：在五个迁移步骤分别注入失败，确认 source 保持 merging、同目标重试完成、异目标冲突。
- [ ] 日志审计：只出现内部 ID/阶段/计数/request id；grep 确认无 Authorization、JWT、guest_id、openid、unionid、完整 profile。
- [ ] 灰度看板：合并开始/完成/恢复/冲突/503 数、`merging` 停留时长、源五表残留数；为长期 merging 设置人工告警阈值。

最终命令：

```bash
cd backend
ruff check app/ tests/
mypy app/
pytest tests/ -q
python -m alembic upgrade head --sql

cd ../miniapp
npm test
npm run type-check
npm run lint:check
npm run build:h5
npm run build:mp-weixin
```

## 7. 精确文件清单

### 新增

- `backend/alembic/versions/20260828_07_account_merge_state.py`
- `backend/app/services/account_merge_service.py`
- `backend/tests/services/test_account_merge_service.py`
- `backend/tests/test_api_v1/test_account_merge.py`
- `backend/tests/test_account_merge_cloudbase_rest.py`

### 修改（后端）

- `backend/app/models/user.py`
- `backend/app/models/__init__.py`（仅在导出新增类型确有需要时）
- `backend/app/schemas/auth.py`
- `backend/app/core/cloud_context.py`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/core/deps.py`
- `backend/app/core/errors.py`
- `backend/app/api/v1/auth.py`
- `backend/app/services/user_service.py`
- `backend/app/repositories/cloudbase_repository.py`
- `backend/app/repositories/cloudbase_rdb.py`（仅当 Repository 新契约需要）
- `backend/.env.example`
- `backend/tests/test_mysql_migrations.py`
- `backend/tests/test_security.py`
- `backend/tests/test_cloudbase_repository.py`
- `backend/tests/test_cloudbase_rdb.py`（仅当底层契约变化）
- `backend/tests/test_cloudbase_rest_services.py`
- `backend/tests/test_api_v1/test_cloud_login.py`
- `backend/tests/test_api_v1/test_guest_login.py`
- `backend/tests/test_api_v1/test_profile.py`、`test_favorite.py`、`test_daily.py`、`test_dining.py`（仅增加合并后回归断言）

### 修改（小程序）

- `miniapp/src/types/api.ts`
- `miniapp/src/api/auth.ts`
- `miniapp/src/api/auth.test.ts`
- `miniapp/src/api/request.test.ts`
- `miniapp/src/auth/storage.ts`
- `miniapp/src/auth/storage.test.ts`
- `miniapp/src/auth/profile-onboarding.ts`
- `miniapp/src/auth/profile-onboarding.test.ts`
- `miniapp/src/stores/user.ts`
- `miniapp/src/stores/user.test.ts`
- `miniapp/src/pages/auth/auth.vue`

不需要新增路由文件或修改 `backend/app/api/v1/__init__.py`：合并复用现有 auth router。不要修改 `implement.jsonl/check.jsonl`，除非主会话在用户批准进入实现前按 Trellis Phase 1.3 单独配置上下文。

## 8. 发布/回滚操作清单

### 发布

- [ ] 生产备份完成且可验证恢复。
- [ ] 先迁移，后部署开关关闭的后端，再发布小程序，最后灰度开关。
- [ ] 验证旧客户端无 token 的 cloud-login、游客登录和现有业务接口。
- [ ] 观察至少一个完整 JWT TTL 周期前，不删除新字段/源 tombstone。

### 停用/回滚

- [ ] 第一动作仅关闭 `ENABLE_GUEST_ACCOUNT_MERGE`，停止新 source 进入 merging。
- [ ] 保留 active-status guard、merged guest 登录拒绝和 merge 恢复入口。
- [ ] 对卡住的 merging 只允许同目标重放；修复脚本先 dry-run 输出内部 ID 和计数，再经人工批准执行。
- [ ] 已有 merged 数据时禁止回滚到“不认识 account_status”的旧后端，禁止 migration downgrade。
- [ ] 需要恢复单个账户时从启用前备份在隔离库重建、人工比对后制定专案；在线自动 unmerge 不在本任务范围。

## 9. 完成门槛

- 所有 AC 有对应自动化测试或明确的实环境证据。
- SQLAlchemy 与 CloudBase REST 固定夹具的归一化最终快照一致。
- 旧游客 JWT 在全部普通受保护接口上均被拒绝，且 guestId 不能兑换正式权限。
- 默认昵称、空头像、跳过资料完善均不影响正式身份。
- 没有真实 CloudBase 私有入口证据时，只能报告“代码与本地契约完成，生产身份边界待验收”，不得把测试 Header 冒充平台背书。
