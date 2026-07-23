# Directory Structure

> miniapp 模块组织规范，配合 `default_package: miniapp` 在 `.trellis/config.yaml`。

---

## Overview

miniapp 是 uni-app + Vue3 + Vite + TypeScript 项目，编译目标是微信小程序（后续可拓展到 H5/支付宝/抖音）。代码组织遵循「页面 → 组件 → store → api → utils」自顶向下的依赖流向，**禁止反向依赖**（utils 不能 import api，api 不能 import store）。

---

## Directory Layout

```
miniapp/
├── src/
│   ├── pages/                 # 页面（对应 pages.json 中的路由）
│   │   ├── today/             # 今日推荐主页
│   │   │   └── today.vue
│   │   ├── profile/            # 用户档案
│   │   │   ├── profile.vue
│   │   │   └── components/      # 仅本页使用的组件
│   │   ├── constitution/      # 体质测试
│   │   ├── history/            # 历史记录
│   │   ├── favorite/          # 收藏夹
│   │   └── mine/               # 我的（tabBar）
│   ├── components/             # 跨页面复用组件（easycom 自动注册）
│   │   ├── FoodCard.vue
│   │   ├── MoodPicker.vue
│   │   └── WeatherBadge.vue
│   ├── stores/                 # Pinia stores
│   │   ├── user.ts             # 用户档案 + token
│   │   ├── daily.ts           # 今日推荐状态
│   │   └── food.ts             # 食物库缓存
│   ├── api/                    # 后端接口封装
│   │   ├── request.ts          # uni.request 拦截器 + 错误处理
│   │   ├── auth.ts             # /auth/*
│   │   ├── profile.ts          # /profile/*
│   │   ├── daily.ts            # /daily/*
│   │   └── food.ts             # /food/*
│   ├── utils/
│   │   ├── date.ts             # 日期格式化、农历
│   │   ├── storage.ts          # wx.storage 包装
│   │   └── share.ts            # 分享卡片生成
│   ├── types/                  # 共享类型定义
│   │   ├── api.ts              # 后端响应类型
│   │   ├── food.ts
│   │   └── user.ts
│   ├── static/                 # 图标、图片（不参与编译）
│   ├── App.vue
│   ├── main.ts
│   ├── pages.json              # 路由 + tabBar + 样式
│   ├── manifest.json           # 微信 appid、权限声明
│   └── env.d.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── uni.config.ts
```

---

## Module Organization

### 新增页面流程

1. 在 `src/pages/<slug>/` 下创建 `<slug>.vue`
2. 在 `src/pages.json` 的 `pages` 数组里追加 `{ "path": "pages/<slug>/<slug>", "style": {...} }`
3. 若是 tabBar 页面，同步加入 `tabBar.list`
4. 在 `src/api/` 找/创建对应接口模块
5. 在 `src/stores/` 找/创建对应 store（如状态跨页面共享）

### 新增组件流程

- 仅本页面用 → 放该页面 `components/` 子目录，组件名带页面前缀
- 跨页面复用 → 放 `src/components/`，用 PascalCase 命名
- uni-ui 组件直接用，无需注册

---

## Naming Conventions

| 类型 | 规则 | 例子 |
|---|---|---|
| 页面目录 | kebab-case | `pages/today/today.vue` |
| 页面文件 | 与目录同名 | `today.vue` |
| 组件文件 | PascalCase | `FoodCard.vue` |
| Store 文件 | camelCase | `user.ts`（导出 `useUserStore`） |
| API 模块 | camelCase | `daily.ts` |
| TS 类型文件 | kebab-case 或单名词 | `api.ts`、`user.ts` |
| 工具函数 | camelCase | `formatDate()` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY` |

---

## Examples

- 页面示例：`src/pages/today/today.vue`
- 组件示例：`src/components/FoodCard.vue`
- Store 示例：`src/stores/user.ts`
- API 封装示例：`src/api/daily.ts`
