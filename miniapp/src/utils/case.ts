/**
 * 字段命名转换工具 - snake_case ↔ camelCase。
 *
 * 设计原则：
 * - 后端 API 用 snake_case（Python PEP 8 + SQL 习惯）
 * - 前端 TS 用 camelCase（JS 社区惯例 + 微信小程序原生 API 一致）
 * - 转换只在 request.ts 一处做，集中维护不扩散
 * - 只转对象 key；不动 value（如 '2024-01-01' 这样的字符串原样保留）
 * - 无下划线的 key（如 id / nickname）原样返回，不误改
 */

type AnyRec = Record<string, unknown>

/**
 * snake_case 字符串 → camelCase。
 * 例：'user_id' → 'userId'，'avatar_url' → 'avatarUrl'，'id' → 'id'。
 */
export function snakeToCamelKey(s: string): string {
  if (!s.includes('_')) return s
  return s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

/**
 * camelCase 字符串 → snake_case。
 * 例：'userId' → 'user_id'，'avatarUrl' → 'avatar_url'，'id' → 'id'。
 */
export function camelToSnakeKey(s: string): string {
  if (!/[a-z][A-Z]/.test(s)) return s
  return s.replace(/([a-z])([A-Z])/g, '$1_$2').toLowerCase()
}

/**
 * 递归把对象所有 key 从 snake_case 转 camelCase。
 * - 数组里每个元素如果是对象，也转
 * - null / 原始值原样返回
 * - 不动 value（值只递归对象/数组结构，不修改字符串本身）
 */
export function snakeToCamel<T>(value: unknown): T {
  if (value === null || value === undefined) return value as T
  if (Array.isArray(value)) {
    return value.map((v) => snakeToCamel(v)) as unknown as T
  }
  if (typeof value === 'object') {
    const obj = value as AnyRec
    const out: AnyRec = {}
    for (const k of Object.keys(obj)) {
      out[snakeToCamelKey(k)] = snakeToCamel(obj[k])
    }
    return out as unknown as T
  }
  return value as T
}

/**
 * 递归把对象所有 key 从 camelCase 转 snake_case。
 * 对称版本，与 snakeToCamel 行为一致。
 */
export function camelToSnake<T>(value: unknown): T {
  if (value === null || value === undefined) return value as T
  if (Array.isArray(value)) {
    return value.map((v) => camelToSnake(v)) as unknown as T
  }
  if (typeof value === 'object') {
    const obj = value as AnyRec
    const out: AnyRec = {}
    for (const k of Object.keys(obj)) {
      out[camelToSnakeKey(k)] = camelToSnake(obj[k])
    }
    return out as unknown as T
  }
  return value as T
}
