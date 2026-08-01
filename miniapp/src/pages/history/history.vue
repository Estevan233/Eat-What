<template>
  <view class="page">
    <text class="page-title">历史记录</text>

    <view v-if="loading" class="hint"><text>加载中…</text></view>

    <view v-else-if="items.length === 0" class="hint">
      <text>还没有历史记录，去推荐几道菜吧～</text>
    </view>

    <view v-else class="list">
      <view v-for="log in items" :key="log.id" class="log-item">
        <view class="log-date">{{ log.logDate }}</view>
        <view class="log-meta">
          <text class="mood-text">{{ moodLabel(log.mood) }}</text>
          <text v-if="log.chosenFoodIds.length" class="chosen-text">
            选了 {{ log.chosenFoodIds.length }} 道
          </text>
          <text v-else class="unselected-text">未选</text>
        </view>
        <text v-if="log.weatherTag" class="weather-text">{{ weatherLabel(log.weatherTag) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useDailyStore } from '@/stores/daily'
import { MOOD_LABELS } from '@/constants/daily'
import { WEATHER_TAG_LABEL } from '@/constants/weather'
import type { DailyLogRead } from '@/api/daily'

const dailyStore = useDailyStore()
const items = ref<DailyLogRead[]>([])
const loading = ref(false)

onShow(async () => {
  loading.value = true
  try {
    const resp = await dailyStore.fetchHistory(30)
    if (resp) {
      items.value = resp.items
    }
  } finally {
    loading.value = false
  }
})

function moodLabel(mood: string): string {
  return (MOOD_LABELS as Record<string, string>)[mood] || mood
}

function weatherLabel(tag: string): string {
  return (WEATHER_TAG_LABEL as Record<string, string>)[tag] || tag
}
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx;
  min-height: 100vh;
  background: $bg;
}

.page-title {
  font-size: 42rpx;
  font-weight: 700;
  color: $ink;
  margin-bottom: 32rpx;
}

.hint {
  padding: 100rpx 0;
  text-align: center;
  color: $ink-3;
  font-size: 28rpx;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.log-item {
  background: $card;
  border: 1rpx solid $line;
  border-radius: $radius-md;
  padding: 28rpx;
  display: flex;
  align-items: center;
  gap: 24rpx;
  box-shadow: $shadow-card;
}

.log-date {
  font-size: 28rpx;
  font-weight: 600;
  color: $ink;
  min-width: 200rpx;
}

.log-meta {
  display: flex;
  gap: 12rpx;
  flex: 1;
}

.mood-text {
  font-size: 24rpx;
  color: $brand-dark;
  background: $brand-light;
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
}

.chosen-text {
  font-size: 24rpx;
  color: $fresh;
}

.unselected-text {
  font-size: 24rpx;
  color: $ink-3;
}

.weather-text {
  font-size: 22rpx;
  color: $ink-2;
  background: $bg;
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
}
</style>