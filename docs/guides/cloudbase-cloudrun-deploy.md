# FastAPI 部署到 CloudBase 云托管

## 1. 最终架构

```text
微信小程序
  -> wx.cloud.callContainer
  -> CloudBase 环境 cloud1-d8gz4jm8vb964a1c9
  -> 云托管服务 eat-what-api:8080
  -> CloudBase MySQL
```

MVP 阶段不需要单独购买 VPS。`callContainer` 负责小程序到同环境云托管服务的调用，也无需把 FastAPI 暴露成一个自购域名的公网 API。

## 2. 固定部署参数

| 参数 | 值 |
|---|---|
| 部署目录 | 仓库中的 `backend` |
| Dockerfile | `backend/Dockerfile` |
| 环境 ID | `cloud1-d8gz4jm8vb964a1c9` |
| 服务名 | `eat-what-api` |
| 监听端口 | `8080` |
| AppID | `wx59c5620b7a894f8e` |
| 最小实例数 | `0` |
| 最大实例数 | `1`（MVP） |
| 初始规格 | `0.25 vCPU / 0.5 GB`，压测后再调整 |

环境分工：

- `cloud1-d8gz4jm8vb964a1c9`：主环境，承载当前小程序和正式数据。
- `tx-clouddev-d3g8w4jpif0222220`：预发/验收环境，不与主环境共用数据库和秘密。

两个环境均已设为手动续费。这能避免到期自动扣费，但不会代替用量预算和告警；到期前应主动决定保留哪个环境。

最小实例数为 0 可以压低闲时费用，但会有冷启动。若真实用户开始抱怨首次登录慢，再用数据决定是否改为 1，别一上来就给空气配豪宅。

## 3. 部署前安全处理

用户曾在聊天中发送过小程序 AppSecret，应立即在微信公众平台重置。旧值视为已经泄露，不要再使用，也不要写入 Git、前端变量或截图。

生成 JWT 密钥（任意可信本地终端均可，推荐 WSL）：

```bash
openssl rand -hex 32
```

这会输出 64 个十六进制字符。它是本项目给登录 Token 签名的独立随机密钥，不需要到微信或腾讯云“申请”，也不能复用 AppSecret/MySQL 密码。生成后直接复制到云托管新版本的 `JWT_SECRET` 环境变量，不要发到聊天、截图或提交到 Git。

Windows PowerShell 也可调用 WSL 生成：

```powershell
wsl -d Ubuntu-22.04 -- openssl rand -hex 32
```

正常的 CloudBase 登录依赖云托管可信身份头，不依赖 `code2session`。因此生产环境设置：

```dotenv
ENABLE_CODE2SESSION=false
```

## 4. 准备 CloudBase MySQL

当前个人版开通云托管私有网络会触发昂贵的套餐升级，不能为了“内网”两个字每月多交一大笔钱。现阶段保留已跑通的外网直连作为**有期限的过渡链路**，不购买私有网络；同时按下面的安全约束收口：

- 为应用创建专用、最小权限数据库账号，不长期使用 root；
- 密码使用独立高强度随机值，不与 JWT/AppSecret 复用；
- 只在云托管服务端环境变量保存连接串；
- 开启预算告警并检查数据库审计/连接日志；
- 完成 CloudBase MySQL HTTPS REST Repository 迁移后立即关闭外网连接。

CloudBase 官方明确提示外网直连只适合开发调试，因此它不是最终生产形态。最终路线不是付费开 VPC，而是先用真实 Server API Key 验证官方 MySQL REST API 的过滤、写入、错误与事务语义，再分模块替换 SQLAlchemy 运行时访问。验证没做完前不凭文档标题脑补接口——数据库不是许愿池。

当前过渡连接串格式：

```dotenv
DATABASE_URL=mysql://USER:URL_ENCODED_PASSWORD@INTERNAL_HOST:3306/DATABASE?charset=utf8mb4
```

应用会把 CloudBase 复制出来的 `mysql://` 自动转为 SQLAlchemy 需要的 `mysql+pymysql://`。两种写法都可，但不要保留 `[DB-USERNAME]` / `[DB-PASSWORD]` 占位符。

密码中的 `@`、`:`、`/`、`#` 等字符必须 URL 编码。数据库应使用 `utf8mb4`。

## 5. 创建云托管服务

在 CloudBase 控制台选择“云托管”并新建服务：

1. 服务名填 `eat-what-api`。
2. 选择从源代码部署。
3. 构建上下文选择仓库的 `backend` 目录。
4. Dockerfile 使用 `backend/Dockerfile`。
5. 容器端口填 `8080`。
6. MVP 设置最小实例数 0、最大实例数 1。

生产环境变量：

```dotenv
ENVIRONMENT=prod
DEBUG=false
PORT=8080
WX_APPID=wx59c5620b7a894f8e
CLOUDBASE_ENV_ID=cloud1-d8gz4jm8vb964a1c9
ENABLE_CODE2SESSION=false
OPEN_METEO_API=https://api.open-meteo.com/v1/forecast
DATABASE_BACKEND=sqlalchemy
```

敏感变量只通过云托管版本的服务端运行时环境变量配置，不写入 Dockerfile、Git 或任何 `VITE_*` 变量：

```dotenv
DATABASE_URL=<CloudBase MySQL 内网连接串>
JWT_SECRET=<至少 32 字节的随机值>
```

这里的 `sqlalchemy` 是当前已经跑通的过渡配置。不要仅因为代码里出现了 REST 客户端，就提前删除 `DATABASE_URL` 或关闭公网 MySQL。

完成 HTTPS Repository 的真实验收并解除代码中的 fail-closed 闸门后，新版本才改为：

```dotenv
DATABASE_BACKEND=cloudbase_rest
CLOUDBASE_DB_API_KEY=<CloudBase Server API Key>
CLOUDBASE_DB_TIMEOUT_SECONDS=5
CLOUDBASE_DB_READ_RETRIES=1
```

`CLOUDBASE_DB_API_KEY` 是 CloudBase 服务端管理密钥，不是微信 AppSecret。它只允许出现在云托管服务端版本环境变量；不得发送到小程序、写入 `VITE_*`、提交 Git 或粘贴到调试日志。切换前先在 Webshell 执行只读验证：

```sh
python /app/scripts/verify_cloudbase_rdb.py
```

脚本只读取一行菜品，并只输出状态、行数、总数和请求号，不打印响应正文或密钥。只有返回 `cloudbase_rdb_read_ok`，且用户隔离、过滤、Upsert、异常和修复流程均验收后，才允许切换生产 Repository 并关闭 MySQL 公网连接。

当前代码会以 `DATABASE_BACKEND_CLOUDBASE_REST_NOT_READY` 拒绝直接启动 REST 生产模式。这是刻意的安全闸门，不是配置故障。

本项目不允许小程序直接读写 MySQL，所有数据都经 FastAPI。生产表的 CloudBase 客户端基础权限应统一设为“无权限”，服务端再按 JWT 用户强制追加 `user_id` 过滤；`foods`、`recipes` 即使是公开数据也先保持服务端代理，避免形成两套访问规则。Server API Key 具备管理员权限，因此代码层用户隔离测试属于上线阻断项。

“服务端环境变量”不等于“前端可见变量”；CloudBase 官方文档说明它们绑定到特定服务版本。如果当前控制台没有单独的“密文”输入类型，就不要把它误称为完整 Secret Manager；对此 MVP，使用服务端版本环境变量即可，但要限制控制台账号权限并避免截图。

### 启动探针报 `connection refused`

如果镜像构建成功，但 Readiness/Liveness 报 `8080 connection refused`，表示 Uvicorn 未成功监听或已退出。先在“部署日志及详情”中找容器的第一条 Python/Uvicorn 错误，不要盯着最后的探针摘要。本项目最常见的启动拦截项是：

- `JWT_SECRET` 未设置或少于 32 字节；
- `DATABASE_URL` 仍是 SQLite、含占位符，或密码未 URL 编码；
- `DEBUG` / `ENABLE_CODE2SESSION` 不是 `false`；
- 云托管服务端口不是 `8080`，或 `PORT` 值带了额外引号。

不要设置前端可见的 `WX_SECRET`。当前正式登录路径不需要它。

同时确认生产配置：

```dotenv
JWT_ALGORITHM=HS256
```

服务会在 `ENVIRONMENT=prod` 时拒绝 SQLite、`DEBUG=true`、`ENABLE_CODE2SESSION=true` 和非 HS256 配置，避免部署页面显示绿色，数据却悄悄写进一次性容器。

## 6. 迁移与容器启动

应用容器只启动 Uvicorn，不在每个实例启动时执行 DDL 或种子导入：

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

首次部署或包含迁移的版本发布时：

1. 发布新镜像，但先不要让用户流量进入新功能。
2. 访问一次 `/health` 唤起实例。
3. 在云托管“实例详情 → Webshell”中进入任一新版本实例。
4. 执行 `/app/scripts/release.sh`，等待 Alembic 和幂等 seed 全部完成。
5. 再执行 `/health` 和业务烟测，然后切换流量。

`release.sh` 只做一次 `alembic upgrade head` 和 `eat-what seed-all`。不要同时在多个实例运行；未来接入 CI 时，应把它变成带数据库锁的一次性发布任务。

## 7. 部署后验证

先确认 release 脚本成功，再在云托管控制台或服务测试入口验证：

```text
GET /health
```

预期返回 2xx 且状态为健康。注意 `/health` 的 `SELECT 1` 只证明连接可用，不证明迁移和种子完整；首次发布还需在 Webshell 执行：

```sh
alembic current
eat-what seed-all
```

随后用小程序通过 `callContainer` 验证：

1. 游客登录；
2. 微信一键登录；
3. 保存个人档案；
4. 获取完整餐盘推荐；
5. 打开菜谱、替换单项、收藏并确认整套餐；
6. 重启/冷启动后检查历史仍存在。
7. 切换“自己做 / 点外卖或到店吃”，检查两条结果不串台；
8. 拒绝定位后手填城市，仍能获取外食方向；
9. 以“喜欢 / 一般 / 避雷”保存店铺＋菜品记录，重新登录后依然存在；
10. 家庭模式分别测试 2、4、6、8 人，依次得到 3、4、5、6 项；重复角色的菜品 ID 不重复，界面同时显示每人和全桌能量估算。

本版本还需连续点击四次“换一套完整餐”和“给我 3 个外食方向”：相邻两批至少更换 2 项，候选充足时 3 项全换；忌口、体质禁忌和明确标记“避雷”的店铺＋菜品不得为了凑数重新混入。

推荐响应会返回标准 `Server-Timing` 响应头，例如：

```text
total;dur=120.4, profile;dur=8.1, weather;dur=0.1, history;dur=23.6,
catalog;dur=31.7, rank;dur=4.8, write;dur=38.5, app;dur=128.9
```

结合 `X-Request-ID` 和云托管日志判断瓶颈：`app` 很小但手机总耗时高，问题在网络/容器唤醒；`weather` 高说明天气快照未命中；数据库阶段高则继续查连接与 SQL。请分别记录冷启动第一次和实例已唤醒后的三次请求，不要拿第一次 1500ms 给所有请求判刑。

如业务不需要公网直连，关闭不必要的公网访问入口。设置费用预算和告警，观察至少一周的调用次数、冷启动延迟、CPU、内存和 MySQL 使用量后再调整规格。

## 8. 前端发布构建

```bash
cd /root/miniapp-trellis/miniapp
npm run build:mp-weixin
test -f dist/build/mp-weixin/app.json && echo "release app.json OK"
! grep -R "localhost:8000" dist/build/mp-weixin
```

微信开发者工具导入：

```text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\build\mp-weixin
```

确认云环境后，依次做编译、预览、真机调试和上传。

本次验证产物：

```text
后端上传包：/root/miniapp-trellis/backend-cloudbase-20260820-v6.zip
微信工具目录：/root/miniapp-trellis/miniapp/dist/build/mp-weixin
```

上传后端包时选择“压缩包”，目标目录留空，Dockerfile 选择“有”；压缩包根目录应直接看到 `Dockerfile`、`pyproject.toml`、`app/`、`alembic/`、`data/` 和 `scripts/`。

2026-08-20 本地校验记录：后端 331 个测试、前端 44 个测试、全量 Ruff、全量 mypy、TypeScript、ESLint、小程序生产构建、Docker 镜像构建和无 AppSecret 容器启动烟测全部通过。上传包 SHA-256 为 6f1b405296d0338f0b5086dc257e11b19fe15f055b158883fe498e03c9c929ff。

## 9. 回滚

- 应用异常：在云托管版本管理中把流量切回上一稳定版本。
- 新版迁移异常：不要直接删除生产表；先停止新版流量，根据迁移内容做向前修复或经过审查的回退。
- 前端异常：在微信公众平台继续保留上一体验版/线上版本，修复后重新上传。

## 10. 官方参考

- [CloudBase 云托管：从源代码部署](https://docs.cloudbase.net/run/deploy/deploy/deploying-source-code)
- [CloudBase 云托管：小程序访问服务](https://docs.cloudbase.net/run/develop/access/mini)
- [CloudBase MySQL 初始化](https://docs.cloudbase.net/database/configuration/db/tdsql/initialization)
- [CloudBase MySQL 直连服务](https://docs.cloudbase.net/database/configuration/db/tdsql/direct-connection)
- [云托管集成 MySQL 与私有网络](https://docs.cloudbase.net/run/develop/resource-integration/mysql)
- [CloudBase MySQL HTTP REST API](https://docs.cloudbase.net/http-api/mysqldb/mysql-restful-api)
- [云托管 Webshell](https://docs.cloudbase.net/run/maintain/webshell)
