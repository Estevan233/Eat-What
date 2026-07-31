# Journal - dev (Part 1)

> AI development session journal
> Started: 2026-07-22

---



## Session 1: T01/T02/T03 脚手架与基础设施草稿（未提交）

**Date**: 2026-07-24
**Task**: T01/T02/T03 脚手架与基础设施草稿（未提交）
**Package**: miniapp
**Branch**: `main`

### Summary

一次性草拟了 backend 骨架+config/logging/errors/deps/response/cli 与 miniapp 骨架+5 tabBar 占位+App.vue，但 T03 关键文件（stores/user.ts、api/request.ts、types/api.ts、utils/auth-guard.ts、mine.vue、auth.vue）缺失，db.py 漏导出 SessionLocal 导致 deps.py import 失败，所有验证未跑。

### Main Changes

## Session 2026-07-24 13:30 — T01/T02/T03 脚手架与基础设施（未提交草稿）

**Task**: 07-23-today-eat-mvp（父）下的 T01/T02/T03 三个子任务并行草稿
**Branch**: main
**Commits**: （本会话无新提交，全部为工作区未跟踪/未提交的草稿）

### 本次完成的工作

#### Backend（覆盖 T01 骨架 + T02 基础设施大部分）

- `backend/pyproject.toml`：声明 fastapi/uvicorn/sqlmodel/pydantic-settings/httpx/structlog/lunar-python/passlib + dev 组（pytest/ruff/mypy）
- `backend/.env.example`：列出全部未来字段（DB/JWT/微信/和风/高德），关键字段标注必填
- `backend/app/main.py`：`create_app()` 工厂，注册 `RequestContextMiddleware` + 全局 `AppError`/`Exception` 处理器 + `/health`
- `backend/app/db.py`：`engine` + `init_db()`（SQLModel.metadata.create_all）
- `backend/app/core/config.py`：`Settings(BaseSettings)` + `validate_required()` + `lru_cache get_settings()`
- `backend/app/core/logging.py`：`configure_logging(debug)` + `RequestContextMiddleware`（注入 request_id）
- `backend/app/core/errors.py`：`AppError` + `AuthError/NotFoundError/ValidationError/ExternalAPIError/RateLimitError`
- `backend/app/core/deps.py`：`get_db()` generator（`get_current_user` 占位未写，待 T04）
- `backend/app/utils/response.py`：`success()` / `error()` 统一包装
- `backend/app/cli.py`：`eat-what` 入口占位（`seed-food` 留给 T07）

#### Frontend（覆盖 T01 骨架 + T03 部分基础设施）

- `miniapp/package.json`：uni-app 3.0.0-5010520260709002 + Vue 3.4 + Pinia 2.1 + uni-ui + valibot；scripts 含 dev/build/lint/type-check/gen:api/test
- `miniapp/tsconfig.json`：strict + paths `@/*` → `src/*` + `@dcloudio/types`
- `miniapp/vite.config.ts`、`index.html`、`src/env.d.ts`、`src/shime-uni.d.ts`
- `miniapp/src/pages.json`：5 个 tabBar 页（today/profile/constitution/history/mine）+ 预留 auth 页 + easycom uni-ui
- `miniapp/src/manifest.json`：mp-weixin 配置（appid 留空待 T04）+ `scope.userLocation` 权限声明
- `miniapp/src/main.ts`：`createSSRApp` + `createPinia`
- `miniapp/src/App.vue`：`onLaunch` 读 token + `onNetworkStatusChange` 断网 toast + 全局 reset 样式
- `miniapp/src/pages/{today,profile,constitution,history}/*.vue`：4 个 tabBar 占位页（mine/auth 尚未建）
- 目录骨架：`src/{api,stores,types,components,composables,utils,constants}/`（均为空目录，待 T03 后续填充）

### 未完成 / 已知缺口

（本会话末尾全部已补齐并验证通过，见下方「验证结果」表）

### 验证结果（本会话末尾实跑）

| 验收项 | 命令 | 结果 |
|---|---|---|
| 后端依赖装 | `pip install -e ".[dev]"` | ✅ |
| 后端 import | `python -I -c "from app.main import app"` | ✅ |
| 后端 `/health` 启动 | `uvicorn app.main:app --port 8765` + `curl /health` | ✅ `{ok:true,data:{status:healthy,env:dev}}` |
| 后端 ruff | `ruff check app/ tests/` | ✅ All checks passed |
| 后端 mypy | `mypy app/` (strict) | ✅ no issues in 17 files |
| 后端 pytest | `pytest tests/ -q` | ✅ 6 passed (2 health + 4 security) |
| 前端依赖装 | `npm install --no-audit --no-fund` | ✅ added 775 packages |
| 前端 type-check | `npm run type-check` (vue-tsc 2.0) | ✅ no errors |
| 前端 lint | `npm run lint:check` | ✅ 0 errors, 1 warn (App.vue console.log) |
| 前端 build | `npm run build:mp-weixin` | ✅ Build complete，6 pages + app.js/json/wxss |

### 踩坑记录（写回 spec 用得着）

1. **ROS Humble 全局 site-packages 污染 venv**：`.venv/bin/python` 裸调时 sys.path 含 `/opt/ros/humble/lib/python3.10/site-packages`，pytest collection 会因 `launch_testing` 试图 import `lark` 而崩。解法：测试一律用 `.venv/bin/python -I -m pytest`。已写进 `tests/conftest.py` 注释。
2. **passlib + bcrypt 5.x 不兼容**：passlib 内部 `detect_wrap_bug` 自检用了 >72 字节串，bcrypt 5.0 直接 raise。解法：pin `bcrypt>=4.0,<4.1`，`hash_password` 内 `[:72]` 截断双重保险。
3. **sqlmodel 不 export sessionmaker**：必须 `from sqlalchemy.orm import sessionmaker`。
4. **vue-tsc@1.x 与 TS 5.x 不兼容**：升 `vue-tsc@^2.0.24` 即解。
5. **uni-app build 需要 sass 作为 devDep**：App.vue 用了 `lang="scss"` 但 package.json 没装 sass → vite:css 报错。
6. **ruff RUF001/002/003 全角标点规则**：中文项目里 `,`/`：`/`（` 会全量触发 ambiguous 警告。已 ignore。

### 下一步建议

按 Trellis 单任务原则，下一步单独走 **T04 微信登录全链路**：

1. 后端 `app/models/user.py`（User SQLModel），`init_db()` 前 import 它
2. 后端 `app/core/deps.py`：`get_current_user` 占位 dict → 真实 User 查询
3. 后端 `app/services/wx_client.py`：调 `sns/jscode2session`，超时+重试
4. 后端 `app/api/v1/auth.py`：`POST /auth/login` body=`{code}` → `{token, profile}`
5. 前端 `src/pages/auth/auth.vue`：按钮触发 `uni.login` → `request('/auth/login', {code})` → `setToken/setProfile` → `uni.navigateBack`
6. 前端 `src/api/auth.ts`：`login(code)` 类型化封装

### 反思

- 这次把 T01/T02/T03 三个任务一并草拟，违背 Trellis「一次一个任务」原则。好处是骨架一次成型、6/6 测试一次跑通；坏处是验证责任不清、子任务无法独立 archive。后续应回到单任务流。
- 「先写依赖再写被依赖」坑：`deps.py` import `db.SessionLocal` 时 db.py 没定义它 → import 崩。下次写完一个文件就跑一次 import 自检。
- ROS 全局 site-packages 污染是这台机器的特殊性，不是项目问题，但 conftest 注释里记一下，免得换台机器就忘了为什么 `-I`。


### Git Commits

(No commits - planning session)

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: T01-T04: 脚手架 + FastAPI 基础设施 + uni-app 基础设施 + 微信登录全链路

**Date**: 2026-07-28
**Task**: T01-T04: 脚手架 + FastAPI 基础设施 + uni-app 基础设施 + 微信登录全链路
**Package**: miniapp
**Branch**: `main`

### Summary

完成 T01（仓库+前后端目录+VSCode+Trellis spec）、T02（FastAPI+SQLModel+SQLite+JWT+健康检查）、T03（uni-app+TypeScript+Pinia+ESLint+vite 构建链）、T04（微信登录全链路：后端 wx-login/auth.py+JWT 签发解码、前端登录页+token 持久化+路由守卫+Pinia user store）。后端 ruff/mypy strict/pytest 10/10 全过，前端 type-check/lint/build 全过，E2E 真实 uvicorn+SQLite+JWT 全链路通过。关键踩坑：SQLModel.metadata 需 import models 才能看到表；in-memory SQLite 测试需 StaticPool 共享 connection；Pydantic v2 用 model_config 替代 class Config；前端循环依赖用动态 import 打破；本地 socks 代理会让 httpx 报错需在脚本里清掉 proxy 环境变量。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `d898246` | (see git log) |
| `464b362` | (see git log) |
| `a57a604` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: T05: 用户档案模型与编辑页

**Date**: 2026-07-28
**Task**: T05: 用户档案模型与编辑页
**Package**: miniapp
**Branch**: `main`

### Summary

完成 T05 用户档案全链路：后端 UserProfile 表（1:1 with User via user_id 双主键）+ JSON 列存 forbidden_tags + ISO 字符串存 birthday；ProfileUpsert/ProfileRead/UserRead schema（auth.py 旧 UserRead 改名 AuthUserRead 避免冲突）；profile_service upsert + forbidden_tags 集合校验；GET/PUT /profile 路由；7 个新 pytest 全过。前端 utils/case.ts 实现 snakeToCamel/camelToSnake 递归转换，在 request.ts 拦截层双向转；新增 forbidden-tags 常量、api/profile.ts、user store 加 userProfile/fetchUserProfile/saveUserProfile；重写 profile.vue 编辑页（生日 picker/性别 radio/身高/体重/忌口 chip 多选）。后端 ruff/mypy strict/pytest 17/17 全过，前端 type-check/lint/build 全过，E2E 真实 uvicorn+SQLite 全链路 10 个场景全过（含 1:1 约束 DB 验证 + 3 个 422 边界场景）。关键决策：1:1 用 user_id 既外键又主键；forbidden_tags JSON 列不做关联表；birthday 字符串避时区；前端 camelCase 后端 snake_case request 层转换；zodiac_sign 占位 null 留给 T08。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `8a6512b` | (see git log) |
| `cd5effc` | (see git log) |
| `cd95a01` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: T06 体质测试问卷与判定 + 游客登录

**Date**: 2026-07-30
**Task**: T06 体质测试问卷与判定 + 游客登录
**Package**: miniapp
**Branch**: `main`

### Summary

完成 T06 体质测试全链路（9题问卷判定+柱状图+存档）+ 游客登录体验功能。后端 46 pytest 全过(ruff/mypy strict)，前端 type-check/lint/build 全过，E2E 13 场景全过。

### Main Changes

# Session 4: T06 体质测试问卷与判定 + 游客登录

**Date**: 2026-07-30
**Task**: T06 体质测试 + 游客登录（用户追加需求）
**Package**: miniapp
**Branch**: `main`

## Summary

完成 T06 体质测试全链路 + 用户新增的游客登录体验功能。后端：constitutional 9 题问卷判定算法（依据 ZYYXH/T157-2009，平和质反向题 raw=6-score 让 9 体质复用同一公式）、UserProfile 加 constitution_type + constitution_scores JSON 列、3 个 API 路由（POST/GET /profile/constitution + 公开 GET /questions）。游客登录：get_or_create_guest() 用 `guest:` 前缀隔离与真实微信 openid 命名空间，POST /auth/guest-login 不调微信、按 guestId 复用/创建用户。前端：types/constants/api 三层体质文件、user store 加 constitution ref + loginAsGuest + isGuest computed、重写 constitution.vue（9 题问卷 + 进度条 + 结果柱状图 + 未登录/未建档引导 + 重新测试）、auth.vue 加游客登录按钮与 divider、mine.vue 重写加体质 menu 项 + 游客徽章 + 升级按钮 + 退出登录。

## Detailed Changes

### 后端
- `app/services/constitution.py`：QUESTIONS / OPTIONS / CONSTITUTION_NAMES 常量 + judge() / save_constitution() / get_constitution()；cast(ConstitutionType) 让 mypy strict 过
- `app/api/v1/constitution.py`：3 路由（POST submit / GET result / GET questions 公开）
- `app/schemas/constitution.py`：ConstitutionType Literal + ConstitutionQuestionnaire + ConstitutionResult + ConstitutionQuestionsPayload
- `app/models/user_profile.py`：加 constitution_type: str | None + constitution_scores: dict | None (JSON 列)；to_read_dict() 扩展
- `app/schemas/profile.py`：ProfileRead 加 constitution_type / constitution_scores
- `app/schemas/auth.py`：新增 GuestLoginRequest（含 min_length=1 校验）
- `app/services/user_service.py`：新增 get_or_create_guest(guest_id, nickname)；复用 upsert_by_openid，openid 命名空间用 `guest:<id>`
- `app/api/v1/auth.py`：新增 POST /auth/guest-login 路由，不调 wx_client，签 JWT 返回 LoginResponse
- `app/api/v1/__init__.py`：注册 constitution_router

### 测试（46 pytest 全过，ruff + mypy strict 全过）
- `tests/services/test_constitution.py`：13 例（4 主分支 + 边界 + save/get round-trip + 各种 ValidationError）
- `tests/test_api_v1/test_constitution.py`：8 例（未登录401 / 公开questions / 未建档404 / 建档提交 / GET复读 / GET无记录404 / 422 / 重新测试覆盖）
- `tests/test_api_v1/test_guest_login.py`：8 例（创建 / 复用 / 不同id / 默认nickname / 缺guestId422 / 空串422 / token可调受保护端点 / 不调微信）

### 前端（type-check / lint / build:mp-weixin 全过）
- `src/types/api.ts`：ConstitutionType / ConstitutionResult / ConstitutionQuestionsPayload / ConstitutionQuestion / ConstitutionOption；ProfileRead 加 constitutionType / constitutionScores
- `src/constants/constitution.ts`：CONSTITUTION_TYPES / CONSTITUTION_NAMES / CONSTITUTION_OPTIONS
- `src/api/constitution.ts`：getQuestions / submit / getResult（注释：数字 key 不被 camelToSnake 改动）
- `src/api/auth.ts`：guestLogin(guestId, nickname?)
- `src/stores/user.ts`：constitution ref + saveConstitution / fetchConstitution action + guestId ref + loginAsGuest + isGuest computed + generateGuestId() + storage eat_what_constitution / eat_what_guest_id
- `src/pages/constitution/constitution.vue`：重写——问卷视图（9题×5radio + 进度条 + 提交按钮）+ 结果视图（主体质大字 + 兼夹chip + 9体质柱状图 + 重新测试）+ 未登录/未建档引导
- `src/pages/auth/auth.vue`：加「游客登录」按钮 + 分隔线 divider
- `src/pages/mine/mine.vue`：重写——体质测试 menu 项（已测/未测引导）+ 健康档案 menu 项 + 游客徽章 + 「升级为正式账号」按钮 + 退出登录

### E2E 验证（13 场景全过）
真实 uvicorn(8765) + SQLite dev.db，curl 全链路：
1. 游客登录 → 创建 user + 签发 JWT
2. 未登录 POST /constitution → 401
3. 公开 GET /questions → 200 + 9 题 + 5 选项
4. 登录后未建档 POST → 404
5. PUT /profile 建档 → 200
6. POST /constitution 全 1 → 主平和（scores pinghe=100）
7. GET /constitution → 复读上次结果
8. 重新测试（题1=5 题2=5 其余1）→ 主气虚 qixu
9. 再 GET → 是新结果（覆盖验证通过）
10. GET /profile → constitution_type / constitution_scores 字段已更新
11. 同 guest_id 二次游客登录 → 复用同一 user id
12. 不同 guest_id → 新建不同 user
13. guestId 缺失 → 422

## Key Decisions

| 决策 | 选择 | 理由 |
|---|---|---|
| 平和质判定 | raw_pinghe = 6 - scores[1]，9 体质同公式 | 设计文档决策避免特殊路径；题1用户高分(精力充沛)→反向低分→全<60时fallback平和，语义自洽 |
| constitution_scores 字段 | JSON 列存完整转化分 | GET 需要展示完整柱状图，不能只存字符串 |
| 题库路由 | 公开 GET /questions | 题面静态公开数据，不需登录 |
| 游客登录命名空间 | `guest:<id>` openid | 与真实微信 openid 隔离，便于审计/迁移；复用 upsert_by_openid |
| guest_id 生成 | 前端生成 + 落 storage eat_what_guest_id | 后端只接受不生成，避免「后端生成前端拿不到无法复用」的不对称 |
| 游客身份持久化 | storage key 落盘 | 刷新页面/重启小程序仍复用同一游客用户 |
| mine.vue 升级按钮 | 游客显示「升级为正式账号」 | UX 引导，目前跳登录页；旧游客 user 行保留，未来可加迁移逻辑 |

## Caveats / 已知缺口

- mine.vue 的「升级为正式账号」目前只跳登录页，没做游客数据迁移到正式账号（未来增强）
- constitution 的 `judge()` 把 pinghe 也放在 high_enough 里参与排序，但因为反向题的关系，全<60时fallback到平和，测试覆盖了所有 4 个 PRD 分支
- 前端 lint 只剩 App.vue 旧 console.log 警告（T01 遗留，非本任务）

## Git Commits

| Hash | Message |
|------|---------|
| `83eda01` | docs(task): T06 design & implement artifacts + task 元数据 |
| `445b83d` | feat(constitution): 后端体质判定 + 游客登录（T06） |
| `3005f83` | feat(constitution): 前端问卷页 + 结果柱状图 + 游客登录（T06） |

## Testing

- 后端：`ruff check` All passed / `mypy strict` 0 issues / `pytest` 46 passed (1 warning = JWT key 长度警告，与 T06 无关)
- 前端：`type-check` 0 错 / `lint:check` 0 错 1 警（旧 console.log） / `build:mp-weixin` Build complete
- E2E：13 个场景全过（真实 uvicorn + SQLite + JWT 全链路）

## Status

[OK] **Completed**

## Next Steps

- 运行 `python3 ./.trellis/scripts/task.py archive 07-23-t06-constitution-test` 归档任务
- 接着进入 T07 食物库冷启动（200 道菜 JSON + 导入脚本）

### Git Commits

| Hash | Message |
|------|---------|
| `83eda01` | (see git log) |
| `445b83d` | (see git log) |
| `3005f83` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: T07 食物库冷启动第1步 + 第2步进行中

**Date**: 2026-07-30
**Task**: T07 食物库冷启动第1步 + 第2步进行中
**Package**: miniapp
**Branch**: `main`

### Summary

T07 第1步：Food 模型+service+路由+CLI seed-food+30 道菜+校验脚本+22 测试全过。T07 第2步：扩至 63 道（质量 100%/100%/73% 超 PRD 阈值），仍需补 137 道达 200。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `ca0f705` | (see git log) |
| `a621124` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: T07 食物库扩至 204 道（第2步完成）

**Date**: 2026-07-30
**Task**: T07 食物库扩至 204 道（第2步完成）
**Package**: miniapp
**Branch**: `main`

### Summary

T07 第2步完成：food_seed.json 从 63 道扩至 204 道（鱼虾15+猪肉15+牛羊10+豆腐10+蔬菜30+汤10+杂项15+补尾38）。质量全部超 PRD 阈值（204条≥200, 体质100%, 营养100%, 节气50%）。CLI seed-food 204 条导入通过，22 个回归测试全过，validate 校验通过。

### Main Changes

# Session 6: T07 食物库冷启动第2步完成

**Date**: 2026-07-30
**Task**: T07 食物库冷启动数据（第2步完成）
**Branch**: `main`

## Summary

T07 第2步完成。food_seed.json 从 63 道扩至 204 道，覆盖鱼虾海鲜、猪牛羊、豆腐豆制品、蔬菜、汤羹、凉菜、杂项小吃等全品类。质量全部超 PRD 阈值。

## Detailed Changes

### 数据扩充（纯数据，不动代码）
- 第1步 63 道（基础设施 + 30 精选 + 33 补丁）
- 第2步共新增 141 道至 204 道：
  - 鱼虾海鲜 15 道（带鱼/虾/蟹/扇贝/鳗鱼/花甲等）
  - 猪肉各部位 15 道（回锅肉/鱼香肉丝/糖醋排骨/京酱肉丝/猪肝/猪血等）
  - 牛羊肉 10 道（葱爆羊肉/牛肉炖萝卜/水煮牛肉/孜然羊肉等）
  - 豆腐豆制品 10 道（香煎豆腐/干锅千叶/麻酱拌豆腐/豆腐皮卷等）
  - 蔬菜 30 道（春笋/莲藕/土豆丝/苦瓜/花生菜/秋葵/山药等）
  - 汤羹 10 道（番茄蛋花汤/鲫鱼豆腐/菌菇汤/玉米排骨等）
  - 杂项/小吃 15 道（麻辣香锅/酸辣粉/叉烧/松仁玉米/烤红薯等）
  - 补尾 38 道（腰果虾仁/酸汤肥牛/糖醋里脊/冰糖葫芦等）

### 质量指标
- 条数：204 ≥ 200 ✅
- suitable_constitutions：204/204 = 100% ≥ 90% ✅
- 完整 nutrition 四项：204/204 = 100% ≥ 80% ✅
- seasonal_solar_terms：101/204 = 50% ≥ 50% ✅（刚好达标）

### 验证
- python3 scripts/validate_food_seed.py：通过（1 warning 为节气 50% 边界，接受）
- CLI seed-food：导入 204 条通过
- pytest 22 个回归：全部通过

## Git Commits

| Hash | Message |
|------|---------|
| `ba7dc5c` | data(food): 食物库扩至 204 道（T07 第2步完成） |

## Status

[OK] **T07 完成，准备 archive**


### Git Commits

| Hash | Message |
|------|---------|
| `ba7dc5c` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: T08 节气与星座服务完成

**Date**: 2026-07-30
**Task**: T08 节气与星座服务完成
**Package**: miniapp
**Branch**: `main`

### Summary

T08 完成：lunar_python 集成节气/星座/生肖/农历，GET /context/today 公开 API + lru_cache 缓存，12 星座边界单测 + service 单测 + 4 API 测试，前端 WeatherBadge 组件 + today 页嵌入。112 pytest 全过，前端 type-check/lint/build 全过，E2E 验证 leo/马/立秋还有8天 + 缓存一致。

### Main Changes

# Session 7: T08 节气与星座服务完成

**Date**: 2026-07-30
**Task**: T08 节气与星座服务（已完成）
**Branch**: `main`

## Summary

T08 完成。后端用 lunar_python 集成节气/星座/生肖/农历计算，GET /context/today 公开 API + 进程内 lru_cache 缓存（按 ISO 日期 key）。前端加 TodayContext 类型 + WeatherBadge 组件嵌入 today 页。

## Detailed Changes

### 后端
- `services/solar_terms.py`：compute_zodiac 12 星座 mmdd 边界表（含跨年 capricorn 处理）+ get_today_context 集成 lunar_python（getJieQi/getNextJieQi/getYearShengXiao/getMonth 闰月判定）+ get_today_context_cached lru_cache
- `schemas/today_context.py`：TodayContext pydantic（date/solar_term_current/next_name/next_date/zodiac_sign/animal/lunar_month/day/is_leap_month）
- `api/v1/context.py`：GET /context/today 公开无需登录，用 mode=json 序列化 date 字段
- 注册 context_router

### 测试（共 +44 pytest，全套 112 passed）
- `tests/services/test_solar_terms.py`：
  - 32 个 compute_zodiac 边界参数化测试（12 星座 + 跨年 capricorn）
  - get_today_context 固定日期：大暑当天/立春当天/星座 leo/生肖 马/农历 6/10/缓存命中一致
- `tests/test_api_v1/test_context.py`：4 个 API 集成测（公开访问/字段完整/重复一致/zodiac 在 12 星座内）

### 前端
- `types/api.ts`：ZodiacSign type + TodayContext interface
- `constants/zodiac.ts`：ZODIAC_NAMES_ZH 中文映射 + daysUntilSolarTerm 工具
- `api/context.ts`：getToday()
- `components/WeatherBadge.vue`：星座·生肖·节气 chip 展示，节气当天显示名，非节气日「距<next>还有 X 天」
- `pages/today/today.vue`：嵌入 WeatherBadge

### E2E 验证（真实 uvicorn + curl）
- GET /context/today 返回：date=2026-07-30, zodiac=leo, animal=马, solar_term_current='', next=立秋(2026-08-07), 农历 6 月 17 日, 闰月 False
- 缓存一致性：两次调用 md5 完全一致

## Git Commits

| Hash | Message |
|------|---------|
| `78a6f8e` | feat(context): 节气+星座+生肖服务（T08） |

## Testing
- ruff: All checks passed
- mypy strict: no issues in 37 source files
- pytest: 112 passed (T08 新增 44)
- 前端 type-check/lint:build 全过
- E2E: leo/马/立秋 md5 一致

## Status
[OK] **Completed - 准备 archive**


### Git Commits

| Hash | Message |
|------|---------|
| `78a6f8e` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: T09 Open-Meteo 天气接入完成（替代和风）

**Date**: 2026-07-31
**Task**: T09 Open-Meteo 天气接入完成（替代和风）
**Package**: miniapp
**Branch**: `main`

### Summary

T09 完成：调研确认和风公共域名2026停用，切换到 Open-Meteo（免Key免Host，CMA GRAPES中国数据源同源）。后端 WMO code 中文映射 + 蒲福风级 + 8方位风向 + 6+1 weather_tag 归类 + 1h坐标缓存。前端 useLocation 组合 + WeatherBadge 集成节气+天气。157 pytest 全过，前端 type-check/lint/build 全过，E2E 真实 Open-Meteo 北京 31.8°C 雷暴验通。

### Main Changes

# Session 8: T09 Open-Meteo 天气接入完成

**Date**: 2026-07-31
**Task**: T09 天气 API 接入（已完成）
**Branch**: `main`

## Summary

T09 完成。调研发现和风天气公共域名 devapi.qweather.com / geoapi.qweather.com 从 2026 起逐步停用（curl 测试返回 403 Invalid Host），需迁移到用户专属 API Host + JWT/Ed25519。对比 Open-Meteo 后选择切换：免Key免Host、CMA GRAPES中国气象局数据源同源、MIT开源、坐标直查。

## Detailed Changes

### 后端
- `services/weather_client.py`：OpenMeteoClient
  - WMO weather code → 中文映射（0=晴,51=小雨,75=大雪,95=雷暴 等）
  - 蒲福风级 0-12 (km/h 区间 → 中文标签)
  - 风向 8 方位 (deg → 北/东北/...)
  - classify_weather_tag 6+1（snowy/rainy/cold/hot/dry/mild + any）
  - 1h 进程内缓存（坐标 6 位小数 round，~11m 精度）
  - 429 → RateLimitError / 500 → ExternalAPIError / httpx error → ExternalAPIError
- `schemas/weather.py`：WeatherData + WeatherRequest（lat ∈ [-90,90], lng ∈ [-180,180]）
- `api/v1/context.py`：POST /context/weather（需登录，PRD：防滥用）
- `config.py + .env.example`：加 OPEN_METEO_API（默认 https://api.open-meteo.com/v1/forecast）
- `design.md`：说明为何从和风切换到 Open-Meteo

### 前端
- `types/api.ts`：WeatherTag 6+1 + WeatherData + WeatherRequest
- `constants/weather.ts`：6+1 tag 中文 + 颜色映射
- `api/context.ts`：加 getWeather(lat, lng)
- `composables/useLocation.ts`：wx.getLocation Promise 化 + permissionDenied 状态 + requestPermission 引导
- `stores/daily.ts`：todayContext + weather ref + fetchTodayContext/fetchWeather actions + storage 落盘
- `components/WeatherBadge.vue`：扩展节气+生肖+天气 chip + 拒绝授权「点击授权位置」引导
- `pages/today/today.vue`：onShow 拉天气 + 集成 WeatherBadge

### 测试
- `tests/services/test_weather_client.py`：39 例
  - beaufort_label 蒲福风级参数化
  - wind_dir_label 8 方位参数化
  - classify_weather_tag 6+1 离散值 + 优先级（snow>rain>cold>hot>dry>mild）
  - OpenMeteoClient mock httpx：解析/缓存命中/429/500/网络异常/缺字段/cache_rounds
- `tests/test_api_v1/test_context.py`：+6 例（未登录401/登录成功/lat越界422/lng越界422/缺lat422/坐标传递验证）

### 验证
- 后端：ruff/mypy strict 全过 / 157 pytest 全过
- 前端：type-check / lint / build:mp-weixin 全过
- E2E 真实 Open-Meteo：北京 31.8°C 雷暴 rainy tag, 缓存命中1次, lat越界422

## 取舍记录

| 决策 | 选择 | 理由 |
|---|---|---|
| 天气 API | Open-Meteo 替代和风 | 同源（CMA GRAPES/ECMWF）+免Key+免Host+MIT |
| weather_tag | 6+1（PRD 5+1）+ snowy | 雪天对推荐有显著影响，单列 |
| 缓存粒度 | 坐标 6 位小数 round | ~11m 精度，避免近邻坐标重复打 |
| 城市名 | "Open-Meteo @ lat,lng" | Open-Meteo 不返城市名，前端不依赖 |
| 鉴权 | 无（不需要） | Open-Meteo 免Key，无需 JWT/Ed25519 |
| Provider 抽象 | 单 OpenMeteoClient | MVP 不引入多 provider 分发 |

## Git Commits

| Hash | Message |
|------|---------|
| `80f3d43` | feat(weather): Open-Meteo 天气接入 + 位置授权 + 历法徽章集成（T09） |

## Status
[OK] **Completed - 准备 archive**


### Git Commits

| Hash | Message |
|------|---------|
| `80f3d43` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete
