# State Management

> Pinia store 分层与持久化规范。

---

## Overview

状态库统一用 **Pinia**（setup 写法）。状态按来源分三类，分别放到不同 store：

| 类别 | 来源 | 存储 | 例子 |
|---|---|---|---|
| Local state | 组件内部 | 组件 `ref()` | 弹窗显隐、表单输入中态 |
| Global state | 跨页面/跨组件共享 | Pinia store（内存） | 当前推荐结果、tabBar 索引 |
| Persisted state | 重启后仍要恢复 | Pinia + `uni.setStorageSync` | 用户 token、profile 缓存 |
| Server state | 来自后端 | Pinia store（内存 + 失效策略） | 食物库、历史记录 |

---

## State Categories

### 1. Local state（组件内 `ref`/`reactive`）

优先用 ref，对象/数组也用 ref 包裹，除非需要解构时用 reactive。Local state 不进 store。

### 2. Global state（Pinia）

跨页面/跨组件共享的运行时数据进 Pinia。命名规范：`useXxxStore`（导出 setup 函数）。

```ts
// src/stores/daily.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/daily'

export const useDailyStore = defineStore('daily', () => {
  const recommendation = ref<Recommendation | null>(null)
  const loading = ref(false)

  async function fetchToday(mood: Mood) {
    loading.value = true
    try {
      recommendation.value = await api.recommend({ mood })
    } finally {
      loading.value = false
    }
  }

  return { recommendation, loading, fetchToday }
})
```

### 3. Persisted state（Pinia + storage）

token、用户档案等需要持久化的状态，**不**用 pinia-persistedstate 插件（uni-app 兼容性差），手动实现：

```ts
// src/stores/user.ts
export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(uni.getStorageSync('token') || null)
  const profile = ref<UserProfile | null>(
    uni.getStorageSync('profile') ? JSON.parse(uni.getStorageSync('profile')) : null
  )

  function setToken(newToken: string) {
    token.value = newToken
    uni.setStorageSync('token', newToken)
  }

  function clear() {
    token.value = null
    profile.value = null
    uni.removeStorageSync('token')
    uni.removeStorageSync('profile')
  }

  return { token, profile, setToken, clear }
})
```

### 4. Server state（带失效策略）

带过期时间的缓存数据：

```ts
const CACHE_TTL = 1000 * 60 * 60 // 1 小时

const lastFetchAt = ref(0)
const data = ref<Food[]>([])

async function ensureFresh() {
  if (Date.now() - lastFetchAt.value > CACHE_TTL) {
    data.value = await api.fetchAll()
    lastFetchAt.value = Date.now()
  }
}
```

---

## When to Use Global State

提升到 store 的判断标准（满足 ≥2 条）：

- [ ] 同一数据被 ≥2 个页面/组件使用
- [ ] 数据需要在页面跳转后保持（避免每次 onLoad 重新拉取）
- [ ] 数据有跨组件的写入操作
- [ ] 数据需要持久化（重启恢复）

**不满足时优先用 composable + ref**，不要把所有东西塞 store。

---

## Server State 同步策略

### 拉取时机

- tabBar 页面 → `onShow` 时检查 TTL，过期才拉
- 子页 → `onLoad` 拉一次，`onShow` 仅做轻量检查
- 用户主动刷新 → 提供「下拉刷新」或「刷新按钮」，绕过缓存

### 失效场景

| 事件 | 失效的 cache |
|---|---|
| 用户修改档案 | 历史记录、今日推荐 |
| 用户收藏/取消收藏 | 收藏列表、今日推荐（影响均衡度） |
| 用户完成体质测试 | 今日推荐、用户 profile |
| 后端推送天气更新（少见） | 天气数据 |

---

## Common Mistakes

- ❌ 在组件 setup 里直接 `uni.request` —— 应该走 `src/api/` + store
- ❌ 多个 store 互相依赖 —— store 之间用 actions 调用，不用 state 读取
- ❌ 把整个 server response 塞 store —— 只保留 UI 需要的字段
- ❌ 持久化整个 store JSON 字符串 —— 只持久化 token、profile 等关键字段
- ❌ 在 store 的 action 里抛错给组件 —— 应 catch 后设 `error` ref
