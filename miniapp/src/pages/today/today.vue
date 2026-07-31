<template>
  <view class="page">
    <view class="header">
      <text class="title">今天吃啥</text>
      <WeatherBadge ref="badgeRef" class="badge" />
    </view>
    <text class="hint">推荐 UI 与历史收藏将在 T11 实现</text>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { onMounted, ref } from 'vue'
import WeatherBadge from '@/components/WeatherBadge.vue'

const badgeRef = ref<InstanceType<typeof WeatherBadge> | null>(null)

onMounted(() => {
  // WeatherBadge 自己 onMounted 拉节气；today 页 onShow 再触发拉天气
  refreshWeatherIfPossible()
})

onShow(() => {
  // 切回 tab 时刷新天气（但缓存 1h 不重打 API）
  refreshWeatherIfPossible()
})

function refreshWeatherIfPossible() {
  // 用 nextTick 等 WeatherBadge mounted 完成后 call method
  setTimeout(() => {
    badgeRef.value?.refreshWeather?.()
  }, 100)
}
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 60vh;
  justify-content: center;
}
.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 30rpx;
}
.title {
  font-size: 48rpx;
  font-weight: 600;
  color: #2563eb;
}
.badge {
  margin-bottom: 8rpx;
}
.hint {
  font-size: 26rpx;
  color: #888;
}
</style>