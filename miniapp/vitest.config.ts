import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

// 纯函数单测不需要启动 uni-app 编译插件；否则 Vitest 会误走小程序构建链。
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
  },
})
