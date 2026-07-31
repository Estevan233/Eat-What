<template>
  <view class="page">
    <text class="page-title">我的收藏</text>

    <view v-if="loading" class="loading-hint">
      <text>加载中…</text>
    </view>

    <view v-else-if="favorites.length === 0" class="empty-hint">
      <text>还没有收藏的菜，去推荐里收藏几道吧～</text>
    </view>

    <view v-else class="list">
      <view v-for="food in favorites" :key="food.id" class="fav-item">
        <view class="fav-info">
          <text class="fav-name">{{ food.name }}</text>
          <text class="fav-meta">{{ food.category }} · {{ food.cookingMethod }}</text>
          <text v-if="food.caloriesKcalPer100g" class="fav-cal">{{ Math.round(food.caloriesKcalPer100g) }}千卡/100g</text>
        </view>
        <text
          class="unfav-btn"
          @click="onUndo(food.id)"
        >取消收藏</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useFavoriteStore } from '@/stores/favorite'

const favoriteStore = useFavoriteStore()
const favorites = computed(() => favoriteStore.favorites)
const loading = computed(() => favoriteStore.loading)

onShow(async () => {
  await favoriteStore.fetchList(true)
})

async function onUndo(foodId: number) {
  try {
    await favoriteStore.toggle(foodId)
    // 从列表中移除（fetchList(true) 太重，本地删即可）
    // 直接强制重新加载
    await favoriteStore.fetchList(true)
    uni.showToast({ title: '已取消收藏', icon: 'none' })
  } catch {
    // 错误 toast 已处理
  }
}
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx;
}

.page-title {
  font-size: 42rpx;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 32rpx;
}

.loading-hint, .empty-hint {
  padding: 100rpx 0;
  text-align: center;
  color: #94a3b8;
  font-size: 28rpx;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.fav-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
  border: 1rpx solid #e5e7eb;
  border-radius: 16rpx;
  padding: 28rpx;
}

.fav-info {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.fav-name {
  font-size: 30rpx;
  font-weight: 600;
  color: #1f2937;
}

.fav-meta {
  font-size: 22rpx;
  color: #6b7280;
}

.fav-cal {
  font-size: 22rpx;
  color: #94a3b8;
}

.unfav-btn {
  font-size: 24rpx;
  color: #dc2626;
  padding: 10rpx 24rpx;
  background: #fef2f2;
  border-radius: 24rpx;
}
</style>