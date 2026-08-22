# 饭卜卜

今天吃啥嘞？Eat-What，卜一卜 → 补一补。

饭卜卜是一款微信小程序，根据人数、做饭/外食场景、心情、活动量、忌口、体质、节气与天气，推荐更合适的一餐。当前 MVP 已具备发布候选能力。

## 已实现功能

- 微信一键登录与游客登录
- 个人健康档案、忌口标签与九种体质测试
- 一人/家庭模式的完整餐盘推荐和单项替换
- 外卖/到店吃方向推荐、店铺＋菜品记录与避雷
- 菜品能量估算、营养摘要、菜谱详情、收藏和备注
- 推荐历史、近期去重和多轮轮换
- 拒绝定位时手动填写城市；天气不可用时降级而不阻断推荐

## 架构

```text
微信小程序（uni-app + Vue 3 + TypeScript）
  -> wx.cloud.callContainer
  -> CloudBase 云托管（FastAPI）
  -> CloudBase MySQL HTTPS REST API
```

生产环境不使用公网 MySQL TCP 连接，也不需要单独购买 VPS。微信 AppSecret 不进入前端、Git 或当前可信身份头登录链路。

## 目录

```text
miniapp-trellis/
├── miniapp/              # uni-app 微信小程序前端
├── backend/              # FastAPI 后端、迁移、种子和测试
├── docs/guides/          # 部署、微信工具和验收指南
├── docs/plans/           # 仍有参考价值的方案记录
├── .trellis/             # Trellis 工程规范与任务记录
└── .opencode/            # opencode 集成
```

## 本地开发

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
eat-what seed-all
uvicorn app.main:app --reload --port 8000
```

### 小程序

```bash
cd miniapp
npm ci
npm run dev:mp-weixin
```

微信开发者工具应导入 `miniapp/dist/dev/mp-weixin`，不要导入仓库根目录或 `miniapp/src`。

## 发布前验证

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/pytest -q

cd ../miniapp
npm run lint
npm run type-check
npm test -- --run
npm run build:mp-weixin
test -f dist/build/mp-weixin/app.json
```

部署后还必须运行 CloudBase REST 读写契约验证和微信开发者工具真实预览；本地测试通过不能代替云端验收。

## 部署与维护

- [CloudBase 云托管部署](docs/guides/cloudbase-cloudrun-deploy.md)
- [Windows 微信开发者工具 + WSL](docs/guides/wechat-devtools-wsl.md)
- [菜谱与完整餐盘验收](docs/guides/meal-recipe-acceptance.md)
- [后端说明](backend/README.md)

发布压缩包、`dist`、`node_modules`、本地数据库、`.env`、微信工具私有配置和 Agent 运行状态都不提交 Git。生产密钥只由 CloudBase 服务端环境变量/API Key 注入。

## License

AGPL-3.0
