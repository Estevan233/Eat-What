<template>
  <view class="page">
    <view class="header">
      <text class="title">今天吃啥</text>
      <WeatherBadge class="badge" />
    </view>
    <text class="hint">推荐 UI 与历史收藏将在 T11 实现</text>
  </view>
</template>

<script setup lang="ts">
import WeatherBadge from '@/components/WeatherBadge.vue'
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