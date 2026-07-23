# Component Guidelines

> Vue 3 单文件组件写法（uni-app + 微信小程序编译）。

---

## Overview

- 使用 `<script setup lang="ts">` 语法糖
- 优先用 Composition API，禁用 Options API（mixins、`this.xxx`）
- 组件通信：父子用 `defineProps` / `defineEmits`；跨层用 Pinia store，禁用 `provide/inject` 除非确有跨多层场景
- 模板用微信小程序兼容写法（注意 `v-if` vs `wx:if` 等差异）

---

## Component Structure

标准组件文件结构（顺序固定）：

```vue
<template>
  <view class="food-card">
    <image class="food-card__img" :src="food.image" mode="aspectFill" />
    <text class="food-card__name">{{ food.name }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Food } from '@/types/food'

interface Props {
  food: Food
  showReason?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showReason: false
})

const reasonText = computed(() => props.food.reason ?? '')
</script>

<style lang="scss" scoped>
.food-card {
  &__img { width: 100%; height: 200rpx; }
  &__name { font-size: 32rpx; color: #333; }
}
</style>
```

---

## Props Conventions

- 必须用 TypeScript interface 定义：`interface Props { ... }`
- 默认值用 `withDefaults(defineProps<Props>(), { ... })`
- 基础类型默认值直接给；对象/数组默认值用工厂函数：`() => []`
- **禁止** 用 `:foo="xxx"` 的运行时默认声明方式
- 复杂 props 用 `defineModel` 双向绑定（uni-app 3.4+）

### Emits

```ts
const emit = defineEmits<{
  (e: 'select', food: Food): void
  (e: 'cancel'): void
}>()
```

---

## Styling Patterns

- 全局样式放 `App.vue` 或 `src/uni.scss`（uni 内置）
- 组件样式必须 `scoped`，使用 BEM 命名：`.block__element--modifier`
- 尺寸用 `rpx`（750 设计稿基准），字体行高同样
- 颜色：直接写 `#333333` / `rgba()`，未来抽到 `uni.scss` 变量后再迁移
- **禁用** `position: fixed` 不带 z-index 协调（多 fixed 层级会冲突）

### 平台差异处理

```vue
<!-- #ifdef MP-WEIXIN -->
<button open-type="getUserInfo" @getuserinfo="onUserInfo">微信授权</button>
<!-- #endif -->
<!-- #ifdef H5 -->
<button @click="onUserInfoH5">H5 模拟</button>
<!-- #endif -->
```

---

## Lifecycle

小程序生命周期优先用 Vue 包装版本：

- 页面：`onLoad` / `onShow` / `onReady` / `onHide` / `onUnload`（来自 `@dcloudio/uni-app`）
- 组件：`onMounted` / `onUnmounted` 即可，不需要 onShow
- 应用：`onLaunch` / `onShow`（仅 App.vue）

```ts
import { onLoad, onShow } from '@dcloudio/uni-app'
onLoad((options) => { /* query 参数 */ })
onShow(() => { /* 每次显示 */ })
```

---

## Accessibility

小程序无障碍支持有限，但以下要做：

- 所有 `<image>` 必须有 `alt` 或 `aria-label`
- 关键交互按钮文案明确（不要「点击这里」）
- 点击区域 ≥ 80rpx × 80rpx（手指触达）
- 表单错误提示用 `uni.showToast({ icon: 'none' })` 或自定义 toast

---

## Common Mistakes

- ❌ 在 `<script setup>` 外用 `this` —— setup 没有 `this`
- ❌ 在子组件里直接修改 props —— 必须通过 emit 通知父级
- ❌ 用 `v-html` —— 小程序不支持，必须用 `rich-text` 组件
- ❌ 在 `onLoad` 同步发多个请求 —— 用 `Promise.all` 并发
- ❌ 用 `setInterval` 不清理 —— `onUnload` 必须 `clearInterval`
- ❌ 把 `<view>` 当 `<div>` 用 absolute 布局 —— 小程序 flex 更稳
