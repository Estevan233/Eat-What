# T05 Implement — 执行计划

## 顺序

### Phase A: 后端模型与基础设施

- [ ] A1. 新建 `backend/app/core/constants.py`，定义 `FORBIDDEN_TAGS` 与 `FORBIDDEN_TAGS_SET`
- [ ] A2. 新建 `backend/app/models/user_profile.py`，定义 `UserProfile` 表
- [ ] A3. 修改 `backend/app/models/__init__.py`，注册 `UserProfile`
- [ ] A4. 修改 `backend/app/schemas/auth.py`，把 `UserRead` 改名 `AuthUserRead`（仅登录响应用）
- [ ] A5. 修改 `backend/app/api/v1/auth.py`，import `AuthUserRead`，`LoginResponse.user` 类型更新
- [ ] A6. 新建 `backend/app/schemas/profile.py`，定义 `ProfileUpsert` / `ProfileRead` / `UserRead`（含 profile 字段）
- [ ] A7. 新建 `backend/app/services/profile_service.py`，实现 `get_profile` / `upsert_profile`（含 forbidden_tags 集合校验）
- [ ] A8. 新建 `backend/app/api/v1/profile.py`，实现 GET/PUT /profile 路由
- [ ] A9. 修改 `backend/app/api/v1/__init__.py`，注册 profile_router

### Phase B: 后端测试

- [ ] B1. 新建 `backend/tests/test_api_v1/test_profile.py`，覆盖 7 个验收场景
- [ ] B2. 跑 `ruff check app/ tests/` → 0 errors
- [ ] B3. 跑 `mypy app/` → 0 issues
- [ ] B4. 跑 `pytest tests/ -q` → all pass（含 T04 旧 10 个 + T05 新 7 个 = 17）

### Phase C: 前端类型与 API

- [ ] C1. 修改 `miniapp/src/types/api.ts`：`UserProfile` 字段已是 camelCase 保留；新增 `ProfileRead` / `UserWithProfile` / `ProfileUpsert`（全 camelCase）
- [ ] C2. 新建 `miniapp/src/constants/forbidden-tags.ts`，导出 `FORBIDDEN_TAGS` 常量数组与 `ForbiddenTag` 类型
- [ ] C3. 新建 `miniapp/src/utils/case.ts`，实现 `snakeToCamel` / `camelToSnake` 递归转换
- [ ] C4. 修改 `miniapp/src/api/request.ts`：success 分支对 `body.data` 调 `snakeToCamel`；发送前对 `opts.data` 调 `camelToSnake`；BASE_URL 不动
- [ ] C5. 新建 `miniapp/src/api/profile.ts`，封装 `getProfile` / `upsertProfile`
- [ ] C6. 修改 `miniapp/src/stores/user.ts`：新增 `userProfile: ref<ProfileRead | null>` + `fetchUserProfile` / `saveUserProfile` action

### Phase D: 前端编辑页

- [ ] D1. 重写 `miniapp/src/pages/profile/profile.vue`：完整表单（生日 picker / 性别 radio / 身高 number / 体重 number / 忌口 chip 多选）+ onLoad 预填 + 提交逻辑
- [ ] D2. 跑 `npm run type-check` → 0 errors
- [ ] D3. 跑 `npm run lint:check` → 0 errors
- [ ] D4. 跑 `npm run build:mp-weixin` → Build complete

### Phase E: 全链路 E2E

- [ ] E1. 启动真实 uvicorn（8765）
- [ ] E2. 写 E2E 脚本（清掉 proxy 环境变量）：登录 → GET /profile (null) → PUT /profile → GET /profile (有数据) → PUT 改 height → GET 验证更新
- [ ] E3. 跑 E2E → 全链路通过
- [ ] E4. 关闭服务，清理临时文件与 dev.db

## 验证命令速查

```bash
# 后端
cd backend && .venv/bin/ruff check app/ tests/ && .venv/bin/python -I -m mypy app/ && .venv/bin/python -I -m pytest tests/ -q

# 前端
cd miniapp && npm run type-check && npm run lint:check && npm run build:mp-weixin

# E2E
cd backend && .venv/bin/uvicorn app.main:app --port 8765 &
# 然后跑 E2E 脚本（清掉 proxy 环境变量）
```

## 回滚点

- A 完成后 → B 失败可单独修后端，不影响前端
- C 完成后 → D 失败可单独修前端
- E 失败 → 多半是 wx_client mock 或 token 问题，回 B 检查
- BASE_URL 不一致是已知现状，不在本任务范围（design 第 6 节）
