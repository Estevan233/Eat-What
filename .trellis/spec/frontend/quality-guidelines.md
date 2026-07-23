# Quality Guidelines

> 前端代码质量基线。

---

## Overview

- Lint：ESLint + `@typescript-eslint` + `eslint-plugin-vue` + `@uni-helper/eslint-plugin-uni`
- 格式化：Prettier（Vue 文件）+ ESLint（冲突项 Prettier 让步）
- 提交前：`npm run lint && npm run type-check` 必须通过
- 测试：MVP 阶段不强制单测，但 utils 与算法相关函数必须有

---

## Forbidden Patterns

### Vue

- ❌ Options API（`export default { data() {...} }`）—— 用 `<script setup>`
- ❌ mixins —— 用 composable
- ❌ `Vue.set` / `this.$set`（Vue2 残留）
- ❌ 在 template 里写复杂表达式超过 2 层嵌套 —— 抽 computed
- ❌ `v-for` 没 `:key`
- ❌ `v-html`（小程序不支持）

### TypeScript

- ❌ `any` 类型
- ❌ 非空断言 `!` 除非确定（如 ref 初始值）
- ❌ `as` 强转（除测试与第三方库边界）
- ❌ `eval` / `Function`

### uni-app / 小程序

- ❌ 直接 `uni.request` 在组件中 —— 走 `src/api/`
- ❌ `console.log` 提交生产 —— 仅 `console.error` 在 catch 内允许
- ❌ 同步 storage 大对象（`uni.getStorageSync`）超过 100KB
- ❌ `setInterval` 不在 `onUnload` 清理
- ❌ 多个页面同时 `uni.showLoading` —— 队列管理或合并提示

---

## Required Patterns

- ✅ 所有 async action 用 try/finally 控制 loading
- ✅ 所有用户操作必须 100ms 内反馈（loading/动画）
- ✅ 错误用 `uni.showToast({ icon: 'none' })` 提示，禁止静默
- ✅ 列表用 `<scroll-view>` + 下拉刷新 + 上拉加载（除非数据量 <20）
- ✅ 关键页面有骨架屏（`<uni-skeleton>` 或自实现）
- ✅ 表单 input 失焦校验 + 提交前整体校验

---

## Testing Requirements

### MVP 阶段（P0）

| 模块 | 要求 |
|---|---|
| `src/utils/` 纯函数 | 必须有 vitest 单测 |
| `src/api/` 封装 | 不强制 |
| 组件 | 不强制 |
| 推荐/打分算法相关逻辑 | 必须有（后端，见 backend spec） |

### 上线后（P1）

- 引入端到端：使用微信开发者工具自动化测试或 `miniprogram-automator`
- 关键页面截图回归

### 测试命令

```bash
npm run test          # vitest run
npm run test:watch    # 监听
npm run test:coverage # 覆盖率
```

---

## Code Review Checklist

提交 PR 前：

- [ ] `npm run lint` 通过
- [ ] `npm run type-check` 通过
- [ ] 无 `console.log` 残留
- [ ] 异步操作有 loading / error UI
- [ ] 文案中文化（产品面向中文用户）
- [ ] tabBar 页面 ≥ 320rpx 高度时布局正常
- [ ] 不同机型测试（iPhone X 安全区、小屏 320px）
- [ ] 网络断开场景：用 `uni.onNetworkStatusChange` 给出提示
- [ ] 新增依赖确认 tree-shaking 友好（避免 `moment.js` 这类大库）
