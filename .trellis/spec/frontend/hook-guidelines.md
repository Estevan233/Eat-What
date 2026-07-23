# Hook / Composition API Guidelines

> Vue 3 Composition API 使用规范（uni-app 上下文）。

---

## Overview

「Hook」在 Vue 3 生态里指 `useXxx` 命名的组合式函数（Composables）。本项目的复用逻辑统一写成 composable，禁止 React-style hooks 模式（不需要 `useEffect` 等）。

适用场景：
- 跨组件复用的有状态逻辑（监听地理位置、网络状态、用户手势）
- 抽象小程序平台 API 的副作用（如 `wx.login` 的回调包装成 Promise）
- 第三方库的初始化与清理

---

## Custom Composable Patterns

文件位置：`src/composables/`（与 `src/utils/` 区分：utils 无状态，composables 有状态）

```ts
// src/composables/useLocation.ts
import { ref, onUnmounted } from 'vue'

export function useLocation() {
  const latitude = ref(0)
  const longitude = ref(0)
  const loading = ref(true)
  const error = ref<string | null>(null)

  let timer: number | null = null

  const refresh = () => {
    loading.value = true
    uni.getLocation({
      type: 'gcj02',
      success: (res) => {
        latitude.value = res.latitude
        longitude.value = res.longitude
        error.value = null
      },
      fail: (err) => {
        error.value = err.errMsg
      },
      complete: () => {
        loading.value = false
      }
    })
  }

  onMounted(refresh)
  onUnmounted(() => {
    if (timer) clearTimeout(timer)
  })

  return { latitude, longitude, loading, error, refresh }
}
```

---

## Data Fetching

不引入 React Query / SWR（uni-app 兼容性差），自封装 `useRequest` composable：

```ts
// src/composables/useRequest.ts
import { ref } from 'vue'

export function useRequest<T>(fn: () => Promise<T>, options?: { immediate?: boolean }) {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref<Error | null>(null)

  const run = async () => {
    loading.value = true
    error.value = null
    try {
      data.value = await fn()
    } catch (e) {
      error.value = e as Error
      uni.showToast({ title: (e as Error).message, icon: 'none' })
    } finally {
      loading.value = false
    }
  }

  if (options?.immediate !== false) run()

  return { data, loading, error, run }
}
```

页面里使用：

```ts
const { data: daily, loading, run: refresh } = useRequest(() => api.daily.recommend({ mood: 'happy' }))
```

---

## Platform API Wrapping

把小程序回调风格 API 包装成 Promise：

```ts
// src/composables/useWxApi.ts
export function promisify<T>(api: (opts: any) => void) {
  return (opts: any): Promise<T> =>
    new Promise((resolve, reject) => {
      api({ ...opts, success: resolve, fail: reject })
    })
}

export const wxLogin = promisify<UniApp.LoginResult>(uni.login)
export const wxGetUserInfo = promisify<UniApp.GetUserInfoResult>(uni.getUserInfo)
```

---

## Naming Conventions

- composable 函数：`use` 前缀 + 名词/动词驼峰：`useLocation`、`useDailyRecommend`
- 文件名：与导出函数同名：`useLocation.ts`
- 返回的 ref 必须有明确类型，禁止 `ref<any>(...)`
- 返回值结构：`{ data, loading, error, run/refresh }` 四件套

---

## Common Mistakes

- ❌ 在 composable 里直接调 store 而不通过 props —— 应保持 composable 纯粹
- ❌ 忘记 `onUnmounted` 清理副作用（定时器、监听器）
- ❌ 在条件分支里调 `onMounted` —— 必须在 setup 顶层调用
- ❌ 多次调用同一个全局监听（如 `uni.onLocationChange`）不去除 —— 引用计数或一次性注册
- ❌ composable 返回纯值而非 ref —— 失去响应性
