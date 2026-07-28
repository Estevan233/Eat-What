# T01 项目脚手架与目录结构

## Goal

为 `miniapp/` 与 `backend/` 创建最小可运行的项目骨架，确保后续任务能在此基础上加业务代码。

## Requirements

### Backend (`backend/`)

- `pyproject.toml`：声明依赖 fastapi、uvicorn[standard]、sqlmodel、pydantic、pydantic-settings、httpx、structlog、lunar-python、valibot(可选)；dev 组：pytest、pytest-asyncio、ruff、mypy
- `app/__init__.py`、`app/main.py`（仅 `app = FastAPI(title="今天吃啥")` + `/health` 端点）
- `app/core/__init__.py`
- `.env.example`：列出所有未来会用到的环境变量（DB、JWT、和风、微信 AppID/Secret、高德 key）
- `app/.gitkeep` 或空目录占位
- `.venv/`、`__pycache__/`、`*.db` 加入 `.gitignore`

### Frontend (`miniapp/`)

- 通过 `npx degit dcloudio/uni-preset-vue#vite-ts miniapp` 或等价方式初始化 uni-app + Vue3 + TS + Vite 模板
- `package.json`：scripts 含 `dev:mp-weixin`、`build:mp-weixin`、`lint`、`type-check`、`gen:api`、`test`
- 安装：vue@^3.4、pinia@^2.1、uni-ui、uview-plus、valibot、openapi-typescript
- dev 依赖：typescript、vite、@types/wechat-miniprogram、eslint、@typescript-eslint/*、eslint-plugin-vue、@uni-helper/eslint-plugin-uni、prettier、vitest
- `tsconfig.json`：strict、paths `@/*` → `src/*`
- `vite.config.ts`：标准 uni-app vite 配置
- `src/pages.json`：tabBar 5 个页（today、profile、constitution、history、mine）+ 临时空白页
- `src/manifest.json`：微信小程序 `mp-weixin` 配置（appid 留空待填）
- `src/main.ts`、`src/App.vue`：最小入口
- 5 个 tabBar 页面占位 `.vue` 文件（仅显示标题）
- `.gitignore`：`node_modules/`、`dist/`、`unpackage/`

### Root

- 仓库根 `.gitignore` 已通过 `trellis init` 处理
- 仓库根 `README.md` 已完成（不需要本任务负责）

## Acceptance Criteria

- [ ] `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` 成功
- [ ] `uvicorn app.main:app` 能启动，`curl http://localhost:8000/health` 返回 `{"ok": true, "data": {"status": "healthy"}}`
- [ ] `cd miniapp && npm install` 成功无 error
- [ ] `npm run type-check` 通过（5 个占位页无 TS 错）
- [ ] `npm run lint` 通过
- [ ] `npm run build:mp-weixin` 生成 `dist/build/mp-weixin/`
- [ ] 用微信开发者工具打开 `dist/build/mp-weixin/` 能看到 5 个 tabBar 页面切换
- [ ] 所有代码遵循 `.trellis/spec/{frontend,backend}/directory-structure.md` 规范
- [ ] 提交后 `git status` 干净

## Dependencies

- 无（首个任务）

## Notes

- 微信 AppID 在本任务先留空字符串，T04 时由开发者填入
- 不安装 alembic、不引入 docker
- 不写任何业务逻辑，仅骨架
