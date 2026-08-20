<template>
  <view class="basis">
    <view class="basis-head">
      <view>
        <text class="title">这套怎么选出来的</text>
        <text class="subtitle">权重总和 100，天气只在节气食养中微调</text>
      </view>
      <text class="weather-limit">天气 ±{{ profile.weatherModifierLimit }}</text>
    </view>
    <view class="rows">
      <view v-for="row in rows" :key="row.label" class="row">
        <text class="label">{{ row.label }}</text>
        <view class="track"><view class="fill" :style="{ width: `${row.value * 4}%` }" /></view>
        <text class="value">{{ row.value }}</text>
      </view>
    </view>
    <text class="disclaimer">{{ disclaimer }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RecommendationWeightProfile } from '@/types/api'

const props = defineProps<{
  profile: RecommendationWeightProfile
  disclaimer: string
}>()

const rows = computed(() => [
  { label: '营养搭配', value: props.profile.nutrition },
  { label: '节气食养', value: props.profile.seasonalWellness },
  { label: '个人/家庭', value: props.profile.personalFamily },
  { label: '偏好历史', value: props.profile.preferenceHistory },
  { label: '做饭可行性', value: props.profile.feasibility },
  { label: '近期多样性', value: props.profile.diversity },
])
</script>

<style lang="scss" scoped>
.basis { padding: 26rpx; border: 1rpx solid $line; border-radius: 28rpx; background: rgba(255, 255, 255, .78); }
.basis-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 20rpx; }
.basis-head > view { display: flex; flex-direction: column; gap: 5rpx; }
.title { color: $ink; font-size: 26rpx; font-weight: 750; }
.subtitle { color: $ink-3; font-size: 18rpx; line-height: 1.4; }
.weather-limit { flex: 0 0 auto; padding: 7rpx 13rpx; border-radius: 999rpx; color: #39714a; background: $fresh-light; font-size: 18rpx; font-weight: 700; }
.rows { display: flex; flex-direction: column; gap: 12rpx; margin-top: 22rpx; }
.row { display: flex; align-items: center; gap: 12rpx; }
.label { width: 124rpx; flex: 0 0 124rpx; color: $ink-2; font-size: 19rpx; }
.track { flex: 1; height: 10rpx; overflow: hidden; border-radius: 999rpx; background: #f1e8de; }
.fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #ffad66, $brand); }
.value { width: 36rpx; color: $ink; font-size: 19rpx; font-weight: 700; text-align: right; }
.disclaimer { display: block; margin-top: 20rpx; padding-top: 16rpx; border-top: 1rpx solid $line; color: $ink-3; font-size: 18rpx; line-height: 1.5; }
</style>
