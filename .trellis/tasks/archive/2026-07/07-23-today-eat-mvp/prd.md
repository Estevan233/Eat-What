# 今天吃啥 MVP — 父任务 PRD

## Goal

构建一款面向「每天不知道吃啥」人群的微信小程序：结合用户的星座、节气、当天天气、心情、个人体质与忌口，用规则+加权打分算法给出 3 道菜的推荐方案，并解释为什么推荐。本父任务管理 MVP 范围（P0 + 体质测试）共 11 个子任务的协调、依赖与最终集成。

## Product Spec 摘要

详见仓库根 `README.md` 与 `.trellis/spec/{frontend,backend,guides}/`。

- **前端**：uni-app + Vue3 + TS + Pinia + uni-ui，编译到微信小程序
- **后端**：FastAPI + SQLModel + SQLite(开发) / PostgreSQL(生产) + JWT 认证
- **第三方数据**：和风天气、`lunar_python` 节气/农历、本地算星座、微信 `wx.getLocation` + 高德逆地理
- **部署**：本阶段不部署，本地开发跑通即可

## Child Tasks

| # | 子任务 | 主要交付物 | 依赖 |
|---|---|---|---|
| T01 | 项目脚手架与目录结构 | `miniapp/` 与 `backend/` 骨架，`pyproject.toml`、`package.json`、`tsconfig.json`、`vite.config.ts`、`pages.json`、`manifest.json` | 无 |
| T02 | FastAPI 基础设施 | `app/main.py`、`core/{config,security,deps,logging}.py`、`db.py`、`/health` 接口 | T01 |
| T03 | uni-app 基础设施 | `src/main.ts`、`App.vue`、`pages.json`、`manifest.json`、`stores/user.ts`、`api/request.ts`、tabBar 5 页占位 | T01 |
| T04 | 微信登录全链路 | `POST /auth/wx-login`、JWT 签发、前端 `wx.login` + token 存储、路由守卫 | T02、T03 |
| T05 | 用户档案模型与编辑页 | `User` 表扩展、`PUT /profile`、档案编辑页（生日/性别/身高/体重/忌口标签） | T04 |
| T06 | 体质测试问卷与判定 | `services/constitution.py`、9 题问卷、判定算法、`POST /profile/constitution`、前端问卷页 | T05 |
| T07 | 食物库冷启动数据 | `data/food_seed.json` 200 道菜、`services/food_seed.py` 导入脚本、`Food` 表与索引 | T02 |
| T08 | 节气与星座服务 | `services/solar_terms.py`（lunar_python 封装）、当前节气、星座、`GET /context/today` | T02 |
| T09 | 和风天气 API 接入 | `services/weather_client.py`（httpx async + 1h 内存缓存）、`GET /context/weather` | T02 |
| T10 | 推荐算法核心 | `services/recommender.py`（规则筛选 + 加权打分 + 理由生成）、`POST /daily/recommend`、单测 | T05、T06、T07、T08、T09 |
| T11 | 今日推荐 UI + 历史记录 + 收藏 | 主页、`DailyLog` 表、`POST /daily/choose`、`GET /history`、收藏接口与页 | T04、T10 |

## Cross-Task Acceptance Criteria（父任务级，子任务归档时不强制）

- [ ] 11 个子任务全部归档
- [ ] 从微信开发者工具登录小程序 → 完成档案 → 体质测试 → 当天获得 3 道菜推荐 → 收藏 → 历史记录能看到
- [ ] 前后端类型同步：跑 `cd miniapp && npm run gen:api` 无 TS 报错
- [ ] `ruff check backend/app && mypy backend/app && pytest backend/tests/` 全绿
- [ ] `cd miniapp && npm run lint && npm run type-check` 全绿
- [ ] 网络断开场景：小程序首页能 fallback 显示上次缓存（不得白屏崩溃）

## Constraints

- 不引入 Redis / Docker / k8s，MVP 阶段所有缓存走进程内
- 不引入 Alembic（开发期用 `SQLModel.metadata.create_all`）
- 不引入第三方登录（仅微信登录）
- 不引入支付
- 不引入消息推送

## Open Questions

- Q1：微信小程序 AppID 是否已申请？影响 T04 的 code2session 调试方式
- Q2：和风天气 API key 是否已申请？影响 T09 的实际接入（可先 mock 开发）
- Q3：BMI 与体质的对应规则需要中医参考来源？建议从《中医体质分类与判定》标准取

## Notes

- 子任务的 `prd.md` 是各自独立的工作单元；父子结构不是依赖系统，依赖在子任务 `prd.md` 顶部声明
- 启动顺序建议：T01 → (T02, T03 并行) → T04 → (T05, T07, T08, T09 并行) → T06 → T10 → T11
- 每个 `task.py start` 前需确保该子任务的依赖已完成或可 mock
