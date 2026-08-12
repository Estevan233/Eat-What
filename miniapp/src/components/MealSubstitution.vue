<template>
  <button class="swap" :disabled="readonly" @click="emit('apply', substitution)">
    <text class="swap-icon">↻</text>
    <view class="swap-copy">
      <text class="swap-title">{{ roleLabel[substitution.targetRole] }}换成 {{ substitution.replacement.name }}</text>
      <text class="swap-reason">{{ substitution.reason }}</text>
    </view>
    <text class="swap-kcal">约 {{ Math.round(substitution.replacement.nutritionPerServing.energyKcal) }} kcal</text>
  </button>
</template>

<script setup lang="ts">
import type { MealRole, MealSubstitution } from '@/types/api'

withDefaults(defineProps<{ substitution: MealSubstitution; readonly?: boolean }>(), {
  readonly: false,
})
const emit = defineEmits<{ apply: [substitution: MealSubstitution] }>()
const roleLabel: Record<MealRole, string> = { main: '主菜', vegetable: '蔬菜', staple: '主食' }
</script>

<style lang="scss" scoped>
.swap { width: 100%; min-height: 92rpx; padding: 18rpx 20rpx; display: flex; align-items: center; gap: 14rpx; text-align: left; background: #fff; border: 1rpx solid $line; border-radius: 22rpx; }
.swap::after { border: none; }
.swap-icon { color: $fresh; font-size: 34rpx; font-weight: 700; }
.swap-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4rpx; }
.swap-title { color: $ink; font-size: 24rpx; font-weight: 650; }
.swap-reason { color: $ink-3; font-size: 20rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.swap-kcal { flex: 0 0 auto; color: $brand-dark; font-size: 21rpx; }
.swap[disabled] { opacity: .45; }
</style>
