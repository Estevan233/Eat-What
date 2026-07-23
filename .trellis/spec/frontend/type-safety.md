# Type Safety

> TypeScript 严格模式 + 运行时校验规范。

---

## Overview

- 项目 `strict: true` 必开，含 `noUnusedLocals` / `noImplicitReturns`
- 编译目标 ES2020（小程序 runtime 兼容）
- 后端类型用 OpenAPI 自动生成（`npm run gen:api`），不手写后端响应类型
- 运行时校验只在外部边界做：用户输入、网络响应

---

## Type Organization

| 类型 | 位置 |
|---|---|
| 后端 API 响应/请求 | `src/types/api.ts`（自动生成 + 手动 patch） |
| 业务实体（Food / UserProfile / Mood） | `src/types/<entity>.ts` |
| Vue 组件 props | 组件文件内 inline interface |
| Store 状态 | store 文件内 inline 类型 |
| 全局共享类型 | `src/types/` |

跨 `miniapp/` 和 `backend/` 共享的类型用 `shared/types/`（待定是否引入，MVP 阶段手抄两边）。

---

## Validation

### 后端响应校验

`src/api/request.ts` 拦截器统一处理：

```ts
// src/api/request.ts
import type { ApiResult, ApiError } from '@/types/api'

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown>
}

export async function request<T>(opts: RequestOptions): Promise<T> {
  const userStore = useUserStore()
  const res = await uni.request({
    ...opts,
    url: `${import.meta.env.VITE_API_BASE}${opts.url}`,
    header: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {}
  })
  // uni.request 返回 [error, response] 元组（uni 3+）
  const [err, response] = res as any
  if (err) throw new Error(err.errMsg)

  const body = response.data as ApiResult<T>
  if (response.statusCode >= 400 || !body.ok) {
    throw new ApiError(body.message, body.code, response.statusCode)
  }
  return body.data
}
```

类型与运行时校验：响应类型来自 `src/types/api.ts`，运行时**只校验关键字段存在**（不信后端但不要过度校验）。复杂对象校验可引入 `valibot`（比 zod 小，兼容性好）。

### 用户输入校验

表单输入在提交前用 valibot schema：

```ts
import { object, string, number, minLength } from 'valibot'

const ProfileSchema = object({
  nickname: string([minLength(1, '昵称必填')]),
  birthday: string(),
  height: number(),
  weight: number()
})

const result = parse(ProfileSchema, formData)
```

---

## Common Patterns

### Type guards

```ts
function isFood(x: unknown): x is Food {
  return !!x && typeof x === 'object' && 'id' in x && 'name' in x
}
```

### Generic API response

```ts
// src/types/api.ts
export interface ApiResult<T> {
  ok: boolean
  data: T
  message?: string
  code?: string
}

export class ApiError extends Error {
  constructor(message: string, public code?: string, public statusCode?: number) {
    super(message)
  }
}
```

### Pinia store 类型

store setup 函数的返回值会被 TypeScript 自动推断，不需要 `defineStore<...>` 显式注解。

---

## Forbidden Patterns

- ❌ `any` —— 用 `unknown` 后 narrowing
- ❌ `as` 断言（除测试代码与三方库返回处）—— 优先 type guard
- ❌ `// @ts-ignore` —— 用 `// @ts-expect-error` 并附注释说明原因
- ❌ 在 store action 里返回 `Promise<any>` —— 必须标 `<T>`
- ❌ 跨边界的对象用 inline 类型 —— 提取到 `src/types/`
- ❌ 用 `Object`/`Function` 作类型 —— 用 `Record<string, unknown>` / `(...args: unknown[]) => unknown`

---

## Backend Type Sync

后端 FastAPI 自动产出 OpenAPI schema，前端通过脚本拉取生成类型：

```bash
# miniapp/package.json
"scripts": {
  "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts"
}
```

后端改了 schema → `npm run gen:api` → 前端编译报错 → 修复 → 防止前后端类型漂移。
