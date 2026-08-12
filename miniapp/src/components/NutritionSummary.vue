<template>
  <view class="nutrition" :class="{ compact }">
    <view class="energy">
      <text class="energy-value">约 {{ Math.round(nutrition.energyKcal) }}</text>
      <text class="energy-unit">kcal / 份</text>
    </view>
    <view class="macro-list">
      <view class="macro"><text>蛋白质</text><text>{{ format(nutrition.proteinG) }}g</text></view>
      <view class="macro"><text>脂肪</text><text>{{ format(nutrition.fatG) }}g</text></view>
      <view class="macro"><text>碳水</text><text>{{ format(nutrition.carbG) }}g</text></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { NutritionTotal } from '@/types/api'

withDefaults(defineProps<{
  nutrition: NutritionTotal
  compact?: boolean
}>(), { compact: false })

function format(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}
</script>

<style lang="scss" scoped>
.nutrition {
  display: flex;
  align-items: stretch;
  gap: 22rpx;
  padding: 24rpx;
  border-radius: 22rpx;
  background: #fff7ef;
  border: 1rpx solid #ffe0c8;
}
.energy { min-width: 170rpx; display: flex; flex-direction: column; justify-content: center; }
.energy-value { color: $brand-deep; font-size: 32rpx; font-weight: 750; }
.energy-unit { color: $ink-2; font-size: 20rpx; margin-top: 4rpx; }
.macro-list { flex: 1; display: flex; gap: 10rpx; }
.macro { min-width: 0; flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 4rpx; color: $ink-2; font-size: 20rpx; }
.macro text:last-child { color: $ink; font-weight: 650; font-size: 24rpx; }
.compact { padding: 18rpx 20rpx; }
.compact .energy-value { font-size: 28rpx; }
@media (max-width: 340px) {
  .nutrition { flex-direction: column; gap: 16rpx; padding: 20rpx; }
  .energy { min-width: 0; flex-direction: row; align-items: baseline; gap: 8rpx; }
  .macro-list { width: 100%; gap: 8rpx; }
}
</style>
