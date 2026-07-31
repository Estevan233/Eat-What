<template>
  <view class="page">
    <view class="header">
      <text class="title">今天吃啥</text>
      <WeatherBadge ref="badgeRef" class="badge" />
    </view>

    <!-- 今日已选提示 -->
    <view v-if="selectedFoodName" class="chosen-hint">
      <text class="chosen-text">今天你选了：{{ selectedFoodName }} ✓</text>
      <navigator url="/pages/favorite/favorite" class="history-link">收藏</navigator>
    </view>

    <!-- 心情选择器 -->
    <view class="selector">
      <text class="selector-label">心情</text>
      <view class="chip-row">
        <text
          v-for="m in MOOD_LIST"
          :key="m"
          class="chip"
          :class="{ 'chip-active': dailyStore.mood === m }"
          @click="dailyStore.setMood(m)"
        >{{ MOOD_LABELS[m] }}</text>
      </view>
    </view>

    <!-- 活动量选择器 -->
    <view class="selector">
      <text class="selector-label">活动量</text>
      <view class="chip-row">
        <text
          v-for="a in ACTIVITY_LIST"
          :key="a"
          class="chip"
          :class="{ 'chip-active': dailyStore.activityLevel === a }"
          @click="dailyStore.setActivityLevel(a)"
        >{{ ACTIVITY_LABELS[a] }}</text>
      </view>
    </view>

    <!-- 主按钮 -->
    <view class="primary-btn" :class="{ 'primary-loading': dailyStore.loading }" @click="onRecommend">
      <text v-if="dailyStore.loading" class="btn-text">推荐中…</text>
      <text v-else class="btn-text">看看今天吃啥</text>
    </view>

    <!-- 骨架屏 -->
    <view v-if="dailyStore.loading" class="skeleton-list">
      <view v-for="i in 3" :key="i" class="skeleton-card" />
    </view>

    <!-- 推荐结果 -->
    <view v-else-if="foods.length" class="food-list">
      <FoodCard
        v-for="food in foods"
        :key="food.id"
        :food="food"
        :chosen="isChosen(food.id)"
        @choose="onChoose"
      />
    </view>

    <!-- 空状态 -->
    <view v-else class="empty-state">
      <text class="empty-text">点击上方按钮，让算法给你推荐 3 道菜</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import WeatherBadge from '@/components/WeatherBadge.vue'
import FoodCard from '@/components/FoodCard.vue'
import { useDailyStore } from '@/stores/daily'
import { useFavoriteStore } from '@/stores/favorite'
import { useUserStore } from '@/stores/user'
import { useLocation, type Coords } from '@/composables/useLocation'
import { MOOD_LABELS, MOOD_LIST, ACTIVITY_LABELS, ACTIVITY_LIST } from '@/constants/daily'
import type { FoodWithReason } from '@/types/api'

const dailyStore = useDailyStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const { getLocation } = useLocation()
const badgeRef = ref<InstanceType<typeof WeatherBadge> | null>(null)

const foods = computed<FoodWithReason[]>(() => {
  return dailyStore.recommendation?.foods || []
})

const selectedFoodName = computed(() => {
  if (!dailyStore.todayLog || dailyStore.todayLog.chosenFoodIds.length === 0) return ''
  const chosenId = dailyStore.todayLog.chosenFoodIds[0]
  const f = foods.value.find((x) => x.id === chosenId)
  return f ? f.name : ''
})

function isChosen(foodId: number): boolean {
  const chosen = dailyStore.todayLog?.chosenFoodIds || []
  return chosen.includes(foodId)
}

async function onRecommend() {
  if (!userStore.isLoggedIn) {
    uni.navigateTo({ url: '/pages/auth/auth' })
    return
  }
  // 尝试拿位置（失败不阻塞，后端用 fallback）
  let coords: Coords | null = null
  try {
    coords = await getLocation()
  } catch {
    // 位置授权失败/拒绝 → 后端 fallback mild
  }
  try {
    await dailyStore.fetchRecommend(coords?.lat, coords?.lng)
    // 刷新天气（block: false）
    if (coords) {
      badgeRef.value?.refreshWeather?.()
    }
    uni.showToast({ title: '推荐完毕', icon: 'none' })
  } catch {
    // toast 已由 request 层处理
  }
}

async function onChoose(food: FoodWithReason) {
  try {
    await dailyStore.chooseFood(food.id)
    uni.showToast({ title: '已记录今日选择', icon: 'success' })
  } catch {
    // toast 已处理
  }
}

onShow(() => {
  // 切回 tab 时：拉今日日志（看用户之前是否选过）
  if (userStore.isLoggedIn) {
    dailyStore.fetchTodayLog()
    favoriteStore.fetchList()
  }
  // 刷新天气（缓存 1h）
  setTimeout(() => {
    badgeRef.value?.refreshWeather?.()
  }, 100)
})
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx;
  display: flex;
  flex-direction: column;
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

.chosen-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ecfdf5;
  border-radius: 12rpx;
  padding: 16rpx 24rpx;
  margin-bottom: 24rpx;
}

.chosen-text {
  font-size: 26rpx;
  color: #047857;
}

.history-link {
  font-size: 24rpx;
  color: #2563eb;
}

.selector {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.selector-label {
  font-size: 26rpx;
  color: #6b7280;
  width: 100rpx;
}

.chip-row {
  display: flex;
  gap: 14rpx;
  flex-wrap: wrap;
}

.chip {
  font-size: 26rpx;
  color: #6b7280;
  background: #f3f4f6;
  border: 1rpx solid #e5e7eb;
  border-radius: 32rpx;
  padding: 10rpx 28rpx;
}

.chip-active {
  color: #ffffff;
  background: #2563eb;
  border-color: #2563eb;
}

.primary-btn {
  background: #2563eb;
  border-radius: 40rpx;
  padding: 24rpx 0;
  text-align: center;
  margin-bottom: 30rpx;
}

.primary-loading {
  background: #94a3b8;
}

.btn-text {
  color: #ffffff;
  font-size: 32rpx;
  font-weight: 600;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  margin-top: 10rpx;
}

.skeleton-card {
  height: 220rpx;
  background: linear-gradient(135deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 18rpx;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.food-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.empty-state {
  padding: 80rpx 0;
  text-align: center;
}

.empty-text {
  font-size: 28rpx;
  color: #94a3b8;
}
</style>