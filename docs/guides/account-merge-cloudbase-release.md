# 微信游客数据合并：CloudBase 发布与真实验收

## 固定目标

- CloudBase 环境：`cloud1-d8gz4jm8vb964a1c9`
- 云托管服务：`eat-what-api`
- 小程序 AppID：`wx59c5620b7a894f8e`
- 后端端口：`8080`
- 数据访问：`DATABASE_BACKEND=cloudbase_rest`
- 小程序访问：`wx.cloud.callContainer`，生产保持公网访问关闭

## 1. 先备份并执行 Schema 迁移

在 CloudBase SQL 编辑器确认 `alembic_version.version_num = '20260820_06'`，完成备份后执行：

```sql
ALTER TABLE users ADD COLUMN account_kind VARCHAR(16) NOT NULL DEFAULT 'wechat';
ALTER TABLE users ADD COLUMN account_status VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN merged_into_user_id INTEGER;
ALTER TABLE users ADD COLUMN merge_started_at DATETIME;
ALTER TABLE users ADD COLUMN merged_at DATETIME;
ALTER TABLE users ADD CONSTRAINT fk_users_merged_into_user_id_users
  FOREIGN KEY (merged_into_user_id) REFERENCES users (id);

UPDATE users SET account_kind = 'guest' WHERE openid LIKE 'guest:%';

CREATE INDEX ix_users_account_kind_status
  ON users (account_kind, account_status);
CREATE INDEX ix_users_merged_into_user_id
  ON users (merged_into_user_id);

UPDATE alembic_version
SET version_num = '20260828_07'
WHERE version_num = '20260820_06';
```

执行后核对：

```sql
SELECT version_num FROM alembic_version;
SHOW COLUMNS FROM users;
SHOW INDEX FROM users;
```

不要执行 downgrade。已经产生 `merging/merged` 用户后回滚旧后端，会让旧游客身份重新获得访问机会。

## 2. 新建 0% 流量版本

使用发布压缩包新建版本，不覆盖现有稳定版本。配置保持：

- `PORT=8080`
- 健康检查：`/health`
- 最小实例数：`0`
- `DATABASE_BACKEND=cloudbase_rest`
- 保留已注入的 `CLOUDBASE_APIKEY`、`JWT_SECRET`、`CLOUDBASE_ENV_ID`
- 不设置 `DATABASE_URL`、`WX_SECRET`
- 新版本部署完成后保持流量 `0%`

## 3. WebShell 真实 CloudBase 合同测试

进入新版本 WebShell，先执行已有读写检查，再执行账户合并检查：

```bash
python /app/scripts/verify_cloudbase_rdb.py --write
python /app/scripts/verify_account_merge_cloudbase.py
```

第二条成功时只输出：

```text
cloudbase_account_merge_contract_ok
```

该脚本会在真实 CloudBase 表中创建随机诊断用户和五类记录，验证条件 PATCH、完整合并、幂等重放和旧游客 Token 失效，并在 `finally` 清理。若失败，先查看堆栈和 CloudBase request id，不要切流。

## 4. 微信开发者工具验收

导入前端目录：

```text
miniapp/dist/build/mp-weixin
```

用测试账号执行：

1. 游客登录；收藏一道菜，生成一次推荐，写一条外食记录并填写健康档案。
2. 点击微信一键登录。
3. 确认返回正式身份，头像昵称完善页可跳过。
4. 确认游客收藏、历史、曝光、外食记录和健康档案仍可见。
5. 重复登录，确认没有重复数据。
6. 检查 Console、Network 与云托管日志，无 401 循环、500、敏感 Header 或环境变量输出。

## 5. 流量与回滚

先通过 URL 定向或小比例灰度，不直接 100%。观察：

- `MERGE_TARGET_CONFLICT`、`MERGE_DATA_CONFLICT`、500 比例；
- `merging` 状态停留时间；
- 登录和推荐 P95 延迟；
- 容器重启、健康检查和 CloudBase REST 错误。

若失败，只把流量切回旧版本并关闭新登录入口；不要 downgrade schema，也不要删除游客 tombstone。

