# T03 uni-app 基础设施

## Goal

在 T01 已生成的 uni-app 项目骨架上，加上真实可用的基础设施层：Pinia、统一请求封装、错误处理、路由守卫、tabBar 页面布局。后续业务任务可以直接写页面与 store。

## Requirements

### `src/main.ts`

```ts
import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

export function createApp() {
  const app = createSSRApp(App)
  app.use(createPinia())
  return { app }
}
```

### `src/App.vue`

- 全局样式（reset、字号、基础色板）
- `onLaunch`：检查本地 token，决定首页 tab 索引
- 监听 `uni.onNetworkStatusChange`，断网时 toast 提示

### `src/api/request.ts`

- 按 spec `type-safety.md` 实现 `request<T>(opts)`
- 自动加 `Authorization: Bearer <token>`（来自 `useUserStore`）
- 401 时清 token 并跳到登录引导
- 统一 toast 错误（除可重试的 5xx，标 loading）
- 超时 10 秒
- 类型：`ApiResult<T>`、`ApiError`

### `src/stores/user.ts`

- 按 spec `state-management.md` 实现
- 状态：`token`、`profile`（含 openid、nickname、avatarUrl、生日、性别、身高、体重、constitution_type、forbidden_tags）
- actions：`setToken`、`setProfile`、`clear`、`isLoggedIn()` computed
- 持久化：`token` 与 `profile` 落 storage

### `src/types/api.ts`

- 手写最小骨架（T01 已生成模板）：
  ```ts
  export interface ApiResult<T> { ok: boolean; code?: string; message?: string; data: T }
  export class ApiError extends Error { code?: string; statusCode?: number }
  export interface UserProfile { id: number; nickname: string; avatarUrl?: string; birthday?: string; gender?: 'male'|'female'|'other'; heightCm?: number; weightKg?: number; constitutionType?: string; forbiddenTags: string[] }
  export interface Mood { value: 'happy'|'neutral'|'tired'|'stressed'|'anxious' }
  ```
- 后续 T04 完成后用 `npm run gen:api` 覆盖

### 5 个 tabBar 页面占位

每页内容：

```vue
<template>
  <view class="page">
    <text class="title">{{ title }}</text>
  </view>
</template>

<script setup lang="ts">
const title = '今日推荐'  // 各页替换
</script>

<style lang="scss" scoped>
.page { padding: 40rpx; }
.title { font-size: 48rpx; font-weight: 600; }
</style>
```

页面：`today`、`profile`、`constitution`、`history`、`mine`

### `src/pages.json`

```json
{
  "pages": [
    {"path": "pages/today/today", "style": {"navigationBarTitleText": "今天吃啥"}},
    {"path": "pages/profile/profile", "style": {"navigationBarTitleText": "档案"}},
    {"path": "pages/constitution/constitution", "style": {"navigationBarTitleText": "体质测试"}},
    {"path": "pages/history/history", "style": {"navigationBarTitleText": "历史"}},
    {"path": "pages/mine/mine", "style": {"navigationBarTitleText": "我的"}}
  ],
  "tabBar": {
    "color": "#888", "selectedColor": "#2563eb",
    "list": [
      {"pagePath": "pages/today/today", "text": "今天"},
      {"pagePath": "pages/profile/profile", "text": "档案"},
      {"pagePath": "pages/constitution/constitution", "text": "体质"},
      {"pagePath": "pages/history/history", "text": "历史"},
      {"pagePath": "pages/mine/mine", "text": "我的"}
    ]
  },
  "globalStyle": {"navigationBarBackgroundColor": "#ffffff", "navigationBarTextStyle": "black"}
}
```

### `src/manifest.json`

- `mp-weixin.appid`：留空 `""`，注释提示 T04 时填
- `mp-weixin.permission.scope.userLocation`：声明 `desc`

### 路由守卫

- `App.vue` `onLaunch`：若 token 不存在 → 不强制跳登录（保留 today 可访问，T04 时改成档案页 push 登录引导）
- 提供工具 `src/utils/auth-guard.ts`：`requireLogin(redirectAfter?: string)`，未登录时 `uni.navigateTo` 到登录页（T04 实现）

### 测试与质量

- `npm run type-check` 通过
- `npm run lint` 通过
- `npm run build:mp-weixin` 通过

## Acceptance Criteria

- [ ] 微信开发者工具打开 `dist/dev/mp-weixin`，5 个 tabBar 页面可切换
- [ ] App.vue 的 `onLaunch` 能正确读到本地 token（用 `uni.getStorageSync` 测）
- [ ] `src/api/request.ts` 能正确加 Authorization header（在 today 页 mock 一个调用验证）
- [ ] 断网时小程序给出 toast 提示（`uni.onNetworkStatusChange`）
- [ ] Pinia store `useUserStore` 可被任意页面读取，且 storage 持久化生效
- [ ] 全部 lint / type-check / build 通过

## Dependencies

- T01（项目骨架）

## Notes

- 本任务**不**实现具体业务 API 调用（如 daily.recommend）
- 本任务**不**实现登录页 UI（T04）
- 登录页路由可以预留 `pages/auth/auth`，但内容空，由 T04 填充
