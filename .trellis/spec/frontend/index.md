# Frontend (miniapp) Development Guidelines

> uni-app + Vue 3 + TypeScript + Pinia + uni-ui, 编译到微信小程序。

---

## Pre-Development Checklist

写代码前快速过一遍，避免子代理写跑偏：

- [ ] 路由在 `src/pages.json` 注册过？跳转用 `uni.navigateTo` 而非 `router.push`。
- [ ] 全局数据走 Pinia store，本地缓存走 `uni.setStorageSync` / `uni.getStorageSync`。
- [ ] 网络请求只通过 `src/api/` 下封装函数，**不要直接在组件里调 `uni.request`**。
- [ ] 平台 API 调用前必须判断 `#ifdef MP-WEIXIN` / `#ifndef H5` 等条件编译。
- [ ] 新组件放 `src/components/`，使用 `easycom` 自动注册（无需 import）。
- [ ] TypeScript 严格模式（`strict: true`）必须打开，禁用 `any`。
- [ ] 样式单位用 `rpx`（响应式），不用 `px`，除非纯 H5 场景。

---

## Quality Check

代码写完后必须满足：

- [ ] `npm run lint` 通过（eslint + @typescript-eslint + uni 标准 rules）。
- [ ] `npm run type-check` 通过（`vue-tsc --noEmit`）。
- [ ] 无 console.* 残留（除 catch 内的 `console.error`）。
- [ ] 所有异步操作都有 loading / error 反馈，不能裸 await。
- [ ] tabBar 页面交互在 100ms 内反馈，长任务用骨架屏。

---

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | miniapp 模块与文件布局 |
| [Component Guidelines](./component-guidelines.md) | Vue 组件写法、props、slot 约定 |
| [Hook Guidelines](./hook-guidelines.md) | Vue 3 Composition API + 生命周期使用 |
| [State Management](./state-management.md) | Pinia store 分层与持久化 |
| [Quality Guidelines](./quality-guidelines.md) | 禁用模式、必用模式、测试要求 |
| [Type Safety](./type-safety.md) | TS 严格模式、类型组织、运行时校验 |

---

## 技术栈固定版本

| 依赖 | 版本范围 | 备注 |
|---|---|---|
| uni-app (vue3) | ^3.0.0-alpha-3000000 | vue3 + vite + ts 模板 |
| vue | ^3.4 | |
| pinia | ^2.1 | |
| typescript | ^5.3 | strict |
| uni-ui | ^1.5 | |
| uview-plus | ^3.1 | 备用组件库 |

---

**语言**：所有 spec 文档使用中文编写，代码注释同。
