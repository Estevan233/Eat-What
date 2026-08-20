<template>
  <view class="card">
    <view class="head">
      <view class="identity">
        <text class="eyebrow">{{ sourceLabel }} · {{ suggestion.category }}</text>
        <text v-if="suggestion.shopName" class="shop">{{ suggestion.shopName }}</text>
        <text class="dish">{{ suggestion.dishName }}</text>
      </view>
      <view class="energy">
        <text class="energy-number">{{ suggestion.energyKcalMinPerPerson }}–{{ suggestion.energyKcalMaxPerPerson }}</text>
        <text class="energy-unit">千卡/人 · 估算</text>
      </view>
    </view>

    <text class="reason">{{ suggestion.reason }}</text>

    <view class="notes">
      <view class="note-row">
        <text class="note-icon">🥗</text>
        <text class="note-text">{{ suggestion.nutritionNote }}</text>
      </view>
      <view class="note-row">
        <text class="note-icon">🌿</text>
        <text class="note-text">{{ suggestion.seasonalNote }}</text>
      </view>
    </view>

    <view class="tips">
      <text v-for="tip in suggestion.orderTips" :key="tip" class="tip">· {{ tip }}</text>
    </view>

    <view class="actions">
      <button class="ghost" @click="copyKeywords">复制搜索词</button>
      <button class="remember" @click="emit('remember', suggestion)">记录店铺＋菜品</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ExternalDiningSuggestion } from '@/types/api'

const props = defineProps<{ suggestion: ExternalDiningSuggestion }>()
const emit = defineEmits<{
  remember: [suggestion: ExternalDiningSuggestion]
}>()

const sourceLabel = computed(() => props.suggestion.source === 'memory' ? '你吃过' : '这次可选')

function copyKeywords(): void {
  uni.setClipboardData({
    data: props.suggestion.searchKeywords.join(' '),
    success: () => uni.showToast({ title: '搜索词已复制', icon: 'none' }),
  })
}
</script>

<style lang="scss" scoped>
.card { padding: 28rpx; border: 1rpx solid $line; border-radius: $radius-lg; background: $card; box-shadow: $shadow-card; }
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 20rpx; }
.identity { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 5rpx; }
.eyebrow { color: $brand; font-size: 20rpx; font-weight: 750; letter-spacing: 1rpx; }
.shop { color: $ink-2; font-size: 22rpx; }
.dish { color: $ink; font-size: 33rpx; font-weight: 800; line-height: 1.25; }
.energy { flex: 0 0 auto; display: flex; flex-direction: column; align-items: flex-end; padding: 10rpx 14rpx; border-radius: 18rpx; background: $brand-light; }
.energy-number { color: $brand-deep; font-size: 22rpx; font-weight: 800; }
.energy-unit { margin-top: 2rpx; color: $brand-dark; font-size: 17rpx; }
.reason { display: block; margin-top: 18rpx; color: $ink-2; font-size: 22rpx; line-height: 1.55; }
.notes { display: flex; flex-direction: column; gap: 10rpx; margin-top: 20rpx; padding: 18rpx; border-radius: 20rpx; background: $bg; }
.note-row { display: flex; align-items: flex-start; gap: 10rpx; }
.note-icon { flex: 0 0 auto; font-size: 22rpx; }
.note-text { flex: 1; color: $ink-2; font-size: 20rpx; line-height: 1.5; }
.tips { display: flex; flex-direction: column; gap: 4rpx; margin-top: 16rpx; }
.tip { color: $ink-3; font-size: 19rpx; line-height: 1.45; }
.actions { display: flex; gap: 12rpx; margin-top: 22rpx; }
.actions button { height: 72rpx; line-height: 72rpx; margin: 0; border-radius: 999rpx; font-size: 22rpx; font-weight: 700; }
.actions button::after { border: none; }
.ghost { flex: 0 0 190rpx; color: $brand; background: $brand-light; }
.remember { flex: 1; color: #fff; background: $brand; }
@media (max-width: 340px) {
  .head { flex-direction: column; }
  .energy { align-items: flex-start; }
  .ghost { flex-basis: 170rpx; }
}
</style>
