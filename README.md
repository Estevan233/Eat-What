# 今天吃啥 · 微信小程序

> 结合用户的星座、节气、天气、心情、体质与忌口，用规则+打分算法给出今天该吃什么的决策建议。

[![Trellis](https://img.shields.io/badge/managed%20by-Trellis-2563eb)](https://github.com/mindfold-ai/Trellis)
[![License](https://img.shields.io/badge/license-AGPL--3.0-16a34a)](./LICENSE)

---

## 项目状态

🚧 MVP 开发中 — 当前阶段：项目脚手架与 spec 填充

---

## 目录结构

```
miniapp-trellis/
├── miniapp/              # uni-app + Vue3 + TS 微信小程序前端
├── backend/              # FastAPI + SQLModel 后端
├── .trellis/             # Trellis 工程框架（spec / tasks / workspace）
├── .opencode/            # opencode 平台集成
└── AGENTS.md             # AI 助手入口
```

---

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | uni-app + Vue 3 + TypeScript + Vite + Pinia + uni-ui |
| 后端 | FastAPI + SQLModel + SQLite(开发) / PostgreSQL(生产) |
| 认证 | 微信 openid → JWT |
| 部署 | uvicorn + Nginx（后期） |

### 第三方数据源

| 数据 | 来源 | 费用 |
|---|---|---|
| 天气 | 和风天气开发版 API | 免费 1000 次/天 |
| 节气/农历 | `lunar_python` 本地计算 | 免费 |
| 星座 | 后端按生日计算 | 免费 |
| 地理位置 | `wx.getLocation` + 高德逆地理 | 微信免费、高德免费 5k/日 |

---

## MVP 范围（P0 + 体质测试）

11 个任务，由 Trellis 管理：

| # | 任务 | 描述 |
|---|---|---|
| T01 | 脚手架 + spec 改写 | uni-app / FastAPI 项目骨架（已完成 spec 部分） |
| T02 | FastAPI 基础设施 | main、Settings、DB、JWT 工具 |
| T03 | uni-app 基础设施 | 项目骨架、Pinia、请求封装、tabBar |
| T04 | 微信登录全链路 | wx.login → code2session → JWT |
| T05 | 用户档案 | 模型 + 编辑页 |
| T06 | 体质测试 | 九种体质问卷 + 判定 |
| T07 | 食物库冷启动 | 200 道菜 JSON + 导入脚本 |
| T08 | 节气 + 星座服务 | lunar_python 集成 |
| T09 | 和风天气 | API 接入 + 1h 缓存 |
| T10 | 推荐算法 | 规则筛选 + 加权打分 + 理由生成 |
| T11 | 今日推荐 UI + 历史收藏 | 主页 + 历史记录 + 收藏 |

详见 `.trellis/tasks/` 下各任务的 `prd.md`。

---

## 快速开始

### 后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # 填配置
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd miniapp
npm install
npm run dev:mp-weixin   # 编译到微信小程序
# 用微信开发者工具打开 dist/dev/mp-weixin
```

### 类型同步

```bash
# 后端启动后
cd miniapp && npm run gen:api   # 从 OpenAPI 拉取 TS 类型
```

---

## Trellis 工作流

本项目由 [Trellis](https://github.com/mindfold-ai/Trellis) 管理，使用 opencode 平台。

```bash
# 查看当前活跃任务
python3 ./.trellis/scripts/task.py current --source

# 列出所有任务
python3 ./.trellis/scripts/task.py list

# 启动某个任务
python3 ./.trellis/scripts/task.py start <task-dir>
```

在 opencode 会话里用 `/trellis:start` 进入开发循环，`/trellis:finish-work` 收尾。

---

## 开发约定

- 前端规范：[`.trellis/spec/frontend/`](./.trellis/spec/frontend/index.md)
- 后端规范：[`.trellis/spec/backend/`](./.trellis/spec/backend/index.md)
- 跨层思考：[`.trellis/spec/guides/`](./.trellis/spec/guides/index.md)
- 工作流：[`.trellis/workflow.md`](./.trellis/workflow.md)

---

## License

AGPL-3.0
