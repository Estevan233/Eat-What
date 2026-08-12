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

最小实例数为 0 可以压低闲时费用，但会有冷启动。若真实用户开始抱怨首次登录慢，再用数据决定是否改为 1，别一上来就给空气配豪宅。

## 3. 部署前安全处理

用户曾在聊天中发送过小程序 AppSecret，应立即在微信公众平台重置。旧值视为已经泄露，不要再使用，也不要写入 Git、前端变量或截图。

生成 JWT 密钥：

```bash
openssl rand -hex 32
```

正常的 CloudBase 登录依赖云托管可信身份头，不依赖 `code2session`。因此生产环境设置：

```dotenv
ENABLE_CODE2SESSION=false
```

## 4. 准备 CloudBase MySQL

在同一个云开发环境中创建 MySQL 实例和数据库，获取内网地址、用户名和密码。容器使用同环境内网连接，连接串格式：

```dotenv
DATABASE_URL=mysql+pymysql://USER:URL_ENCODED_PASSWORD@INTERNAL_HOST:3306/DATABASE?charset=utf8mb4
```

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
```

敏感变量通过控制台密文配置：

```dotenv
DATABASE_URL=<CloudBase MySQL 内网连接串>
JWT_SECRET=<至少 32 字节的随机值>
```

不要设置前端可见的 `WX_SECRET`。当前正式登录路径不需要它。

## 6. 容器启动顺序

Dockerfile 启动时依次执行：

1. `alembic upgrade head`
2. `eat-what seed-all`
3. `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}`

`seed-all` 是幂等的，会准备 205 道菜和 60 份逐人份菜谱。MVP 最大实例数为 1，启动时迁移尚可接受；将来扩容到多实例前，应把数据库迁移拆成独立发布任务，避免多个容器争抢迁移。

首次部署日志应能看到数据库升级到最新迁移，以及菜品/菜谱种子完成。启动异常时从日志里的第一条异常查起，不要只盯着最后一条连锁报错。

## 7. 部署后验证

先在云托管控制台或服务测试入口验证：

```text
GET /health
```

预期返回 2xx 且状态为健康。随后用小程序通过 `callContainer` 验证：

1. 游客登录；
2. 微信一键登录；
3. 保存个人档案；
4. 获取完整餐盘推荐；
5. 打开菜谱、替换单项、收藏并确认整套餐；
6. 重启/冷启动后检查历史仍存在。

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

## 9. 回滚

- 应用异常：在云托管版本管理中把流量切回上一稳定版本。
- 新版迁移异常：不要直接删除生产表；先停止新版流量，根据迁移内容做向前修复或经过审查的回退。
- 前端异常：在微信公众平台继续保留上一体验版/线上版本，修复后重新上传。

## 10. 官方参考

- [CloudBase 云托管：从源代码部署](https://docs.cloudbase.net/run/deploy/deploy/deploying-source-code)
- [CloudBase 云托管：小程序访问服务](https://docs.cloudbase.net/run/develop/access/mini)
- [CloudBase MySQL 初始化](https://docs.cloudbase.net/database/configuration/db/tdsql/initialization)
