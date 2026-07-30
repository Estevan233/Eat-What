# T06 Implement — 执行计划

## 顺序

### Phase A: 后端模型与 service

- [x] A1. `backend/app/models/user_profile.py`：加 `constitution_type: str | None` + `constitution_scores: dict | None` (JSON 列)；扩展 `to_read_dict()`
- [x] A2. `backend/app/schemas/profile.py`：`ProfileRead` 加 `constitution_type` / `constitution_scores` 字段
- [x] A3. 新建 `backend/app/schemas/constitution.py`：`ConstitutionType` Literal + `ConstitutionQuestionnaire` + `ConstitutionResult` + `ConstitutionQuestionsPayload`
- [x] A4. 新建 `backend/app/services/constitution.py`：`QUESTIONS` / `OPTIONS` / `CONSTITUTION_NAMES` 常量 + `judge()` / `save_constitution()` / `get_constitution()` 函数；cast `ConstitutionType` 让 mypy strict 过
- [x] A5. 新建 `backend/app/api/v1/constitution.py`：3 个路由（POST submit / GET result / GET questions）
- [x] A6. `backend/app/api/v1/__init__.py`：注册 constitution_router

### Phase B: 后端测试

- [x] B1. 新建 `backend/tests/services/__init__.py`
- [x] B2. 新建 `backend/tests/services/test_constitution.py`：13 个 service 单测（含 4 个主分支 + 边界 + save/get round-trip）
- [x] B3. 新建 `backend/tests/test_api_v1/test_constitution.py`：8 个 API 集成测（含未登录 401 / 公开 questions / 未建档 404 / 建档提交 / 覆盖 / 422）
- [x] B4. 跑 ruff / mypy strict / pytest → 全绿（46 passed）

### Phase G: 游客登录（用户追加需求）

- [x] G1. 后端 `services/user_service.py` 加 `get_or_create_guest()`（`guest:` 前缀隔离命名空间）；`schemas/auth.py` 加 `GuestLoginRequest`；`api/v1/auth.py` 加 `POST /auth/guest-login` 路由
- [x] G2. 前端 `api/auth.ts` 加 `guestLogin(guestId, nickname?)`；`stores/user.ts` 加 `guestId` ref + `loginAsGuest()` action + `generateGuestId()` 工具；`auth.vue` 加「游客登录」按钮 + divider
- [x] G3. 新建 `backend/tests/test_api_v1/test_guest_login.py`：8 个测试（创建/复用/不同 id/默认 nickname/缺 guestId 422/空串 422/token 可调受保护端点/不调微信）
- [x] G4. `stores/user.ts` 加 `isGuest` computed；`mine.vue` 显示游客徽章 + 「升级为正式账号」按钮 + 退出登录

### Phase C: 前端类型与 API

- [x] C1. `miniapp/src/types/api.ts`：加 `ConstitutionType` / `ConstitutionQuestionnaire`（未用，路由直接吃 dict） / `ConstitutionResult` / `ConstitutionQuestionsPayload` / `ConstitutionQuestion` / `ConstitutionOption`；扩展 `ProfileRead` 加 `constitutionType` / `constitutionScores`
- [x] C2. 新建 `miniapp/src/constants/constitution.ts`：`CONSTITUTION_TYPES` / `CONSTITUTION_NAMES` / `CONSTITUTION_OPTIONS`
- [x] C3. 新建 `miniapp/src/api/constitution.ts`：`getQuestions` / `submit` / `getResult`（注释：数字 key 不被 camelToSnake 改动）
- [x] C4. `miniapp/src/stores/user.ts`：加 `constitution` ref + `saveConstitution` / `fetchConstitution` action + storage `eat_what_constitution`

### Phase D: 前端问卷页

- [x] D1. 重写 `miniapp/src/pages/constitution/constitution.vue`：问卷视图 + 结果视图（柱状图） + 未登录/未建档引导 + 进度条 + 重新测试
- [x] D2. 改 `miniapp/src/pages/mine/mine.vue`：加体质测试 menu 项 + 已测/未测引导 + 升级为正式账号 + 退出登录
- [x] D3. 跑 type-check / lint:check / build:mp-weixin → 全绿（type-check 0 错；lint 0 错 1 警告，警告为 App.vue 旧 console.log；build 成功）

### Phase E: 全链路 E2E

- [x] E1. 启动真实 uvicorn（8765）+ dev.db 重建
- [x] E2. 13 个 E2E 场景全过：游客登录 / 未登录 401 / 公开 questions / 未建档 404 / 建档 / POST 全1 平和 / GET 复读 / 覆盖 qixu / GET /profile 字段已更新 / 同 guest_id 复用 / 不同 guest_id 新建 / guestId 缺失 422
- [x] E3. 关闭服务，清理 dev.db 与临时脚本

## 验证命令

```bash
# 后端（全过）
cd backend && .venv/bin/ruff check app/ tests/ && .venv/bin/python -I -m mypy app/ && .venv/bin/python -I -m pytest tests/ -q
# → All checks passed! / Success: no issues found in 30 source files / 46 passed, 1 warning

# 前端（全过）
cd miniapp && npm run type-check && npm run lint:check && npm run build:mp-weixin
# → 0 错 / 0 错 1 警告（旧 App.vue console.log）/ Build complete
```

## 回滚点

- A 完成后 → B 失败可单独修 service 算法
- C 完成后 → D 失败可单独修前端
- E 失败 → 多半是 wx_client mock 或 token 问题

## 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 平和质判定 | raw_pinghe = 6 - scores[1]，9 体质同公式 | 设计文档决策，避免特殊路径；题1 用户高分（精力充沛）→ 反向低分 → 全 < 60 时 fallback 平和，语义自洽 |
| constitution_scores 字段 | JSON 列存完整转化分 | GET 需要展示完整结果，不能只存字符串 |
| 题库路由 | 公开 GET /questions | 题面是静态公开数据，不需登录 |
| 游客登录命名空间 | `guest:<id>` openid | 与真实微信 openid 隔离，便于审计/迁移；复用 upsert_by_openid 不写重复逻辑 |
| guest_id 生成 | 前端生成 + 落 storage | 后端只接受 guestId 不生成，避免「后端生成前端拿不到无法复用」的不对称 |
| 游客身份持久化 | eat_what_guest_id storage key | 刷新页面 / 重启小程序仍复用同一游客用户 |
| mine.vue 升级按钮 | 游客显示「升级为正式账号」 | UX 引导，目前只是跳登录页（升级后旧的游客 user 行会保留，未来可加迁移逻辑） |
