# 饭卜卜微信登录开发交接

## 先看结论

这不是“已上线完成”的功能，而是一个**本地测试通过、真实 CloudBase 验收失败并已回滚**的功能分支。

- 功能分支：`codex/recommendation-v6-auth`
- 基线：GitHub `main` 提交 `4c23bae`
- 生产状态：已回退到上一正常版本
- 失败版本：`eat-what-api-021`
- 直接故障：生产 `users` 表未执行迁移 07，真实 REST 报 `column merged_at not found`
- 禁止事项：没有执行迁移 07 前，不得再次给新后端分配生产流量

## 权威仓库与目录

- 共享真相：GitHub 仓库 `Estevan233/Eat-What`
- 日常主仓库：WSL `/root/miniapp-trellis`
- 本功能 WSL 工作树：`/root/miniapp-trellis-worktrees/recommendation-v6-auth`
- Windows 下不再保留本功能 worktree、发布 ZIP 或迁移临时文件

其他 agent 开始前必须先执行：

```bash
cd /root/miniapp-trellis-worktrees/recommendation-v6-auth
git status --short --branch
git log -1 --oneline
```

不要在 `C:\Users\Estevan\Documents\devlop\.worktrees` 继续开发。

## 已实现内容

### 身份与数据库状态

- `users` 增加：
  - `account_kind`: `guest | wechat`
  - `account_status`: `active | merging | merged`
  - `merged_into_user_id`
  - `merge_started_at`
  - `merged_at`
- 合并后保留游客 tombstone，普通接口拒绝旧游客 JWT。
- 修复 SQLAlchemy identity map 与 CloudBase REST 旧快照把 tombstone 写回 active 的并发问题。

### 游客转微信正式账号

`POST /api/v1/auth/cloud-login` 使用两份凭证：

- 目标身份：CloudBase 私有链路注入并校验的微信 OpenID。
- 源身份：当前 `Authorization: Bearer <guest JWT>`。

合并数据：

- `favorites`
- `recommendation_events`
- `daily_logs`
- `dining_memories`
- `user_profiles`

规则：正式数据优先，游客只补缺；同一目标可重试，异目标返回冲突。

### 小程序会话切换

- 登录成功前保留游客 Token 与 guestId。
- 正式登录成功后写入正式 Token，清除 guestId 和陈旧健康缓存。
- `isGuest` 改由服务端 `accountKind` 判断，不再通过本地 guestId 猜测。
- 昵称、头像完善仍可跳过，不影响正式身份。

## 已执行的本地验证

最后一次完整验证结果：

- 后端 pytest：`394 passed`
- 后端 Ruff：通过
- 后端 mypy：通过（68 个源文件）
- 前端 Vitest：`72 passed`
- 前端 TypeScript：通过
- 前端 ESLint：通过
- `build:mp-weixin`：通过

这些只能证明本地契约，不代表 CloudBase 真实环境通过。

## 当前真实环境失败

CloudRun WebShell：

```text
CloudBaseRdbError: column merged_at not found in table ...users
```

这表明代码版本先于数据库 Schema 上线。微信登录和游客登录都会操作 `users`，所以一起失败。

## 下一位 agent 的固定工作顺序

### 1. 先确认生产仍在正常旧版本

不要立即重新部署。确认微信登录和游客登录已经恢复。

### 2. 备份并检查 Schema

在 CloudBase MySQL DMC 执行：

```sql
SELECT version_num FROM alembic_version;
SHOW COLUMNS FROM users;
SHOW INDEX FROM users;
```

只有确认当前版本和字段状态后，才能执行迁移。迁移来源：

```text
backend/alembic/versions/20260828_07_account_merge_state.py
```

### 3. 在测试/影子环境执行迁移，不要直接赌生产

若没有独立测试环境，至少先备份，再在生产 DMC 执行生成的 07 SQL，执行后检查五个字段、两个索引、自引用外键和 `alembic_version=20260828_07`。

### 4. 新建 0% 流量版本

- `PORT=8080`
- 健康检查 `/health`
- `DATABASE_BACKEND=cloudbase_rest`
- 保留 `CLOUDBASE_APIKEY`、`JWT_SECRET`、`CLOUDBASE_ENV_ID`
- 不设置 `DATABASE_URL`、`WX_SECRET`
- 公网访问保持关闭

### 5. 必须跑真实合同测试

WebShell：

```bash
python /app/scripts/verify_cloudbase_rdb.py --write
python /app/scripts/verify_account_merge_cloudbase.py
```

第二条只有输出以下内容才算通过：

```text
cloudbase_account_merge_contract_ok
```

脚本使用随机诊断用户和五类临时记录，并在 `finally` 清理。若失败，保留完整堆栈和 CloudBase request id；不得只改本地 fake 测试后宣布修复。

### 6. 微信开发者工具实测

1. 游客登录并产生收藏、推荐、历史、外食记录、健康档案。
2. 微信一键登录。
3. 核对五类数据仍属于正式账号。
4. 重复登录，不得产生重复记录。
5. 使用旧游客 Token 调普通接口，应返回 401。
6. Console、Network 和云日志不得出现 500、401 循环或敏感 Header。

## 尚未完成

- 未在真实 CloudBase 上通过迁移 07。
- 未通过真实账户合并合同测试。
- 未完成微信开发者工具游客→微信全链路。
- 未合并 `main`。

## 同轮另外两个任务的真实状态

### rules_v6

只有 PRD、设计、审计和实施计划，**没有修改推荐生产代码**。入口：

```text
.trellis/tasks/08-28-recommendation-v6/
```

### 500+ 候选库

只有数据审计、字段设计和分批实施计划，**没有修改 food seed 或外食候选数据**。入口：

```text
.trellis/tasks/08-28-candidate-catalog-500/
```

下一位 agent 不得把上述两个任务标成 implemented/completed。

