<template>
  <view class="page">
    <text class="title">{{ title }}</text>
    <text class="hint">页面占位 · {{ hint }}</text>
  </view>
</template>

<script setup lang="ts">
const title = '今天吃啥'
const hint = 'T11 任务会实现推荐 UI'
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
.title {
  font-size: 48rpx;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 20rpx;
}
.hint {
  font-size: 26rpx;
  color: #888;
}
</style>
