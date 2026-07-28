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
