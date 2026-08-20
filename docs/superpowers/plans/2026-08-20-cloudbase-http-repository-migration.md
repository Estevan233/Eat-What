# CloudBase MySQL HTTPS Repository 迁移计划

日期：2026-08-20

状态：REST 客户端与安全闸门已实现；全表 Repository 和生产切换待真实 Server API Key 验收

## 目标与边界

- 目标链路：微信小程序 → `callContainer` → FastAPI → CloudBase MySQL HTTPS REST API。
- 保留 FastAPI 的鉴权和业务规则；所有用户表查询由服务端强制附加 `user_id`。
- Server API Key 只存云托管服务端环境变量，绝不进入小程序、Git、镜像和日志。
- 小程序不直连 MySQL；生产表的客户端基础权限统一为“无权限”，全部经 FastAPI 代理。
- Alembic 继续作为表结构真相源；HTTPS REST 只替换生产运行时 CRUD，不负责自动建表。
- 真实验收前保持 `DATABASE_BACKEND=sqlalchemy`，不关闭当前公网 MySQL。
- 当前设置 `DATABASE_BACKEND=cloudbase_rest` 会被生产配置校验明确拒绝，避免未迁完的 service 误写默认 SQLite。

## 已确认的官方语义

- 表级 REST 支持 GET、POST、PATCH、DELETE、过滤、排序、分页和返回计数。
- Upsert 使用 `Prefer: resolution=merge-duplicates`，冲突依据主键或唯一索引。
- 无过滤的更新在服务端会被拒绝；本地客户端也先行拒绝无过滤更新和删除。
- 单个批量插入请求具备原子性，但多次 HTTP 请求不构成数据库事务。
- CloudBase MySQL SDK/HTTP 通路不能替代原生 MySQL 的跨表事务。

## 分阶段迁移

| 阶段 | 表/能力 | 策略 | 通过条件 |
|---|---|---|---|
| 0 | `foods`、`recipes` | 只读 shadow | REST 与 SQLAlchemy 行数、主键和抽样字段一致 |
| 1 | `user_profiles`、`favorites`、`dining_memories` | 按用户读写 | 所有查询强制 `user_id`；唯一键 Upsert 与错误码验收 |
| 2 | `recommendation_events`、`daily_logs` | 事件为真相、日报为可修复投影 | 唯一请求号幂等；故障注入后可重放修复 |
| 3 | 登录与用户 | 最后迁移 | OpenID 唯一约束、并发首次登录和 Token 回归通过 |
| 4 | 生产切换 | 新版本灰度 | 健康检查、核心烟测、日志与延迟达标后再关闭公网 MySQL |

## 推荐写入的事务替代

当前 SQLAlchemy 实现用一个数据库事务写 `recommendation_events` 和 `daily_logs`。REST 模式不能假装两次 HTTP 调用是事务，因此改成：

1. 以唯一 `request_id` Upsert 推荐事件，事件是权威记录。
2. 以 `(user_id, log_date)` Upsert 今日日志投影，并记录事件 ID。
3. 若第二步失败，客户端不得把结果宣布为“已保存的新一套”；后台或管理脚本按事件安全重放投影。
4. 写请求不做盲重试；只有具备唯一幂等键的 Upsert 才允许重放。

## 云端切换门槛

- [x] 控制台创建 Server API Key，开启云托管“API Key 设置”，由平台自动注入 `CLOUDBASE_APIKEY`；不在普通 Key-Value 环境变量中重复粘贴明文。
- [ ] Webshell 运行 `python /app/scripts/verify_cloudbase_rdb.py`，只读通过且日志无密钥。
- [ ] 真实验证 `eq/in/order/limit/count` 与 400/401/403/404/500/503 错误语义。
- [ ] 在预发环境验证唯一键 Upsert、并发冲突、事件重放和用户隔离。
- [ ] 备份生产数据库，记录 Alembic revision、表行数与抽样校验值。
- [ ] 发布 `DATABASE_BACKEND=cloudbase_rest` 灰度版本并完成微信端核心烟测。
- [ ] 观察至少一个完整业务周期后关闭 MySQL 公网连接。

## 回滚

- 应用异常：流量切回上一稳定版本，恢复 `DATABASE_BACKEND=sqlalchemy`。
- 投影不一致：停止 REST 写入，以推荐事件重建对应 `daily_logs`，禁止直接删生产数据。
- 认证失败：撤销受影响的 Server API Key，创建新 Key 并更新服务版本；不要把 Key 打进工单截图。
