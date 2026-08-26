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
| 最大实例数 | `5`（按需扩容上限，不代表常驻 5 个实例） |
| 初始规格 | `0.25 vCPU / 0.5 GB`，压测后再调整 |

环境分工：

- `cloud1-d8gz4jm8vb964a1c9`：主环境，承载当前小程序和正式数据。
- `tx-clouddev-d3g8w4jpif0222220`：预发/验收环境，不与主环境共用数据库和秘密。

两个环境均已设为手动续费。这能避免到期自动扣费，但不会代替用量预算和告警；到期前应主动决定保留哪个环境。

最小实例数为 0 可以压低闲时费用，但会有冷启动。最大实例数 5 只是流量突增时的上限；没有请求时不会常驻 5 个实例。若真实用户开始抱怨首次登录慢，再用数据决定是否把最小实例改为 1，别一上来就给空气配豪宅。

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

## 4. CloudBase MySQL 的上线形态

最终运行时链路已经切换为 CloudBase MySQL HTTPS REST Repository，不购买私有网络，也不需要单独搬一份数据库：表和数据仍是当前 `cloud1` 环境中的同一个 MySQL，只是 FastAPI 从公网 TCP/SQLAlchemy 改为官方 HTTPS API。

保留数据库“自动暂停”为开启状态。具体空闲暂停窗口以控制台当前显示为准；它会带来首次访问冷启动，但能降低学生项目的闲时费用。本项目同时保证：

- 云托管最小实例数保持 `0`、最大实例数 `5`；
- `/health` 只检查进程是否存活，不查询 MySQL，避免探针反复唤醒数据库；
- 首页先展示本地上次推荐，再后台刷新；天气失败降级为中性权重，不阻断主推荐；
- 热实例缓存 10 分钟的只读菜品/菜谱目录，不缓存用户档案、收藏或历史。

表结构仍由 Alembic 管理，HTTPS REST 只负责运行时 CRUD，不负责 DDL。现有生产库已执行到当前 revision 并导入幂等种子，因此本次切换不再运行数据搬迁。以后新增字段时，必须先通过受控 SQL 连接、CloudBase SQL 编辑器或一次性发布任务执行迁移，再发布依赖新字段的 REST 版本。

## 5. 创建云托管服务

在 CloudBase 控制台选择“云托管”并新建服务：

1. 服务名填 `eat-what-api`。
2. 选择从源代码部署。
3. 构建上下文选择仓库的 `backend` 目录。
4. Dockerfile 使用 `backend/Dockerfile`。
5. 容器端口填 `8080`。
6. MVP 设置最小实例数 0、最大实例数 5。

生产环境变量：

```dotenv
ENVIRONMENT=prod
DEBUG=false
PORT=8080
WX_APPID=wx59c5620b7a894f8e
CLOUDBASE_ENV_ID=cloud1-d8gz4jm8vb964a1c9
ENABLE_CODE2SESSION=false
QWEATHER_API_HOST=<和风天气控制台分配的专属 API Host，不含路径>
QWEATHER_TIMEOUT_SECONDS=2.5
DATABASE_BACKEND=cloudbase_rest
CLOUDBASE_DB_TIMEOUT_SECONDS=5
CLOUDBASE_DB_READ_RETRIES=1
```

敏感变量只通过云托管版本的服务端运行时环境变量配置，不写入 Dockerfile、Git 或任何 `VITE_*` 变量：

```dotenv
JWT_SECRET=<至少 32 字节的随机值>
QWEATHER_API_KEY=<和风天气服务端 API Key>
```

`QWEATHER_API_HOST` 与 `QWEATHER_API_KEY` 都只供 FastAPI 服务端使用。小程序不直接调用天气供应商，也不配置高德或 Open-Meteo。后端按 0.1° 网格复用 1 小时新鲜缓存；和风调用失败时最多复用 12 小时的最近成功数据并标记“缓存天气”，完全无缓存才返回中性天气，不阻断餐食推荐。

当前为减少凭据数量，使用仍受支持的 WebAPI v7 API Key 请求头鉴权。和风已提示 v7 城市实况“即将弃用”；升级到 v1 前应先在测试环境验证其 JWT/Ed25519 鉴权，再替换接口，不能把私钥下发到小程序。页面需持续显示“天气服务：和风天气 · qweather.com”来源标注。

发布后在 Cloud Run WebShell 做一次不打印密钥的连通性检查（只显示 HTTP 状态和总耗时）：

```sh
python -c "import os,time,httpx; h=os.environ['QWEATHER_API_HOST'].rstrip('/'); k=os.environ['QWEATHER_API_KEY']; t=time.perf_counter(); r=httpx.get(f'{h}/v7/weather/now', params={'location':'116.41,39.92','lang':'zh','unit':'m'}, headers={'X-QW-Api-Key':k}, timeout=2.5); print('status=',r.status_code,'elapsed_ms=',round((time.perf_counter()-t)*1000))"
```

成功门槛是 `status=200`，并连续执行 3 次记录耗时。不要打印响应头、完整响应或环境变量值；若超时，应用仍会使用 12 小时 last-good/neutral 降级，但本次版本不能宣称真实天气链路已验收。

在部署版本页面打开“API Key 设置”，选择已创建的 `Eat-What` Server API Key。平台会自动注入标准环境变量 `CLOUDBASE_APIKEY`，不需要也不应在普通 Key-Value 环境变量中再复制一份明文。代码也兼容显式变量 `CLOUDBASE_DB_API_KEY`，但它只用于本地验证或平台自动注入不可用时的回退。

Server API Key 不是微信 AppSecret。它只允许出现在云托管服务端运行环境；不得发送到小程序、写入 `VITE_*`、提交 Git 或粘贴到调试日志。切换前先在 Webshell 只检查变量是否存在，不要打印变量值：

```sh
python -c "import os; print('CLOUDBASE_APIKEY=' + ('SET' if os.getenv('CLOUDBASE_APIKEY') else 'MISSING'))"
```

预期输出 `CLOUDBASE_APIKEY=SET`。随后依次执行只读与写入验证：

```sh
python /app/scripts/verify_cloudbase_rdb.py
python /app/scripts/verify_cloudbase_rdb.py --write
```

第一条验证 `eq`、`in`、排序、分页和精确计数；第二条在 `users` 表插入一条随机诊断记录、按主键更新并在 `finally` 中删除。脚本只输出状态和请求号，不打印响应正文、OpenID 或密钥。必须同时看到 `cloudbase_rdb_read_ok` 和 `cloudbase_rdb_write_ok`。若写入仍返回 403，先检查 Server API Key 与表级写权限，不要把客户端权限粗暴改成“所有用户可写”。

新 REST 版本不得配置 `DATABASE_URL`。回滚应在云托管版本管理中切回上一稳定版本，不能把公网连接串重新塞进当前版本假装修复 REST 错误。HTTP Repository 写入验收和微信端灰度通过后，CloudBase MySQL 公网访问保持关闭；自动暂停开关继续开启。

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

### `callContainer` 报 `access_token missing`

这类错误由微信/CloudBase 网关在请求进入 FastAPI 前返回。先在微信开发者工具 Console 直接执行：

```js
wx.cloud.callContainer({
  config: { env: 'cloud1-d8gz4jm8vb964a1c9' },
  path: '/health',
  method: 'GET',
  header: { 'X-WX-SERVICE': 'eat-what-api' },
  success: console.log,
  fail: console.error,
})
```

- 如果仍为 `access_token missing`，不要重部署 FastAPI。确认开发者工具登录的是该小程序开发者账号，在“云开发控制台 → 设置 → 环境设置 → 管理我的环境”中导入/关联 `cloud1-d8gz4jm8vb964a1c9`，然后“清缓存 → 全部清除”、退出并重新登录开发者工具，再重新编译。
- 如果 `/health` 返回 2xx，再检查 `/api/v1/auth/cloud-login` 和云托管日志；这才属于后端登录链路。

构建产物必须从 `miniapp/dist/build/mp-weixin` 导入，`project.config.json` 的 AppID 应为 `wx59c5620b7a894f8e`。重置微信 AppSecret 后仍保持 `ENABLE_CODE2SESSION=false`、`WX_SECRET` 为空；当前可信身份头登录不读取 AppSecret。

服务会在 `ENVIRONMENT=prod` 时拒绝 SQLite、`DEBUG=true`、`ENABLE_CODE2SESSION=true` 和非 HS256 配置，避免部署页面显示绿色，数据却悄悄写进一次性容器。

## 6. 迁移与容器启动

应用容器只启动 Uvicorn，不在每个实例启动时执行 DDL 或种子导入：

```text
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

本次数据库已由上一 SQLAlchemy 版本执行 Alembic 和幂等 seed，不要在 `DATABASE_BACKEND=cloudbase_rest` 的新实例里再次执行 `/app/scripts/release.sh`；它是 DDL 发布工具，需要原生数据库连接，不是应用启动步骤。

上线顺序：

1. 保留上一稳定 SQLAlchemy 版本，记录当前 Alembic revision 和数据表行数。
2. 发布 REST 新版本，但先只给测试流量。
3. 在 Webshell 确认 `CLOUDBASE_APIKEY=SET`，依次运行只读验证和 `python /app/scripts/verify_cloudbase_rdb.py --write`。
4. 验证 `/health`、登录、档案、推荐、收藏、外食记录、确认套餐和历史。
5. 切换全部流量并观察一个业务周期；稳定后关闭 MySQL 公网地址。

未来确有结构迁移时，先在旧 SQLAlchemy 版本或受控发布任务执行 `/app/scripts/release.sh`，再部署 REST 应用版本；不要让多个实例同时跑迁移。

## 7. 部署后验证

先确认云托管版本启动正常；只有本次确实包含表结构变更时才检查受控迁移任务。普通 REST 版本不要运行 `release.sh`。随后在云托管控制台或服务测试入口验证：

```text
GET /health
```

预期返回 2xx，且 `data.status=healthy`、`data.database=lazy-rest`。`/health` 刻意不访问数据库；数据库契约由 `verify_cloudbase_rdb.py` 和业务烟测验证。把数据库查询塞进高频探活，会让自动暂停形同虚设，属于花钱买“绿色监控”的反向理财。

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

微信工具目录固定为：

```text
/root/miniapp-trellis/miniapp/dist/build/mp-weixin
```

后端优先从仓库中的 `backend` 目录做源代码部署。若控制台必须上传压缩包，应在仓库外临时生成；压缩包根目录直接包含 `Dockerfile`、`pyproject.toml`、`app/`、`alembic/`、`data/` 和 `scripts/`。发布包可由源码重新生成，因此不要提交 Git，也不要用文件名里的 v10、v11 猜当前线上版本。

每次发布都重新运行后端测试、Ruff、mypy、前端测试、TypeScript、ESLint、小程序生产构建、Docker 构建与 CloudBase REST 写入契约验证，并在部署记录中保存当次提交 SHA、云托管版本号和包摘要。旧测试数量和旧压缩包摘要不属于长期文档资产。

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
