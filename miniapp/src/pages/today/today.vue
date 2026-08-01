<template>
  <view class="page">
    <!-- 英雄区 -->
    <view class="hero">
      <image class="hero-avatar" src="/static/brand-avatar.png" mode="aspectFill" />
      <view class="hero-text">
        <text class="hero-title">今天吃啥</text>
        <text class="hero-sub">结合天气 · 节气 · 心情 · 体质</text>
      </view>
      <WeatherBadge ref="badgeRef" class="badge" />
    </view>

    <!-- 今日已选提示 -->
    <view v-if="selectedFoodName" class="chosen-banner">
      <text class="chosen-mark">✓</text>
      <text class="chosen-text">今天你选了：{{ selectedFoodName }}</text>
      <navigator url="/pages/favorite/favorite" class="fav-link">收藏 ›</navigator>
    </view>

    <!-- 输入区 -->
    <view class="panel">
      <view class="panel-row">
        <text class="panel-label">心情</text>
        <view class="chip-row">
          <text
            v-for="m in MOOD_LIST"
            :key="m"
            class="chip"
            :class="{ 'chip-on': dailyStore.mood === m }"
            @click="dailyStore.setMood(m)"
          >{{ MOOD_EMOJI[m] }} {{ MOOD_LABELS[m] }}</text>
        </view>
      </view>
      <view class="panel-row">
        <text class="panel-label">活动量</text>
        <view class="chip-row">
          <text
            v-for="a in ACTIVITY_LIST"
            :key="a"
            class="chip"
            :class="{ 'chip-on': dailyStore.activityLevel === a }"
            @click="dailyStore.setActivityLevel(a)"
          >{{ ACTIVITY_EMOJI[a] }} {{ ACTIVITY_LABELS[a] }}</text>
        </view>
      </view>

      <view class="cta" :class="{ 'cta-loading': dailyStore.loading }" @click="onRecommend">
        <text v-if="dailyStore.loading" class="cta-text">正在为你搭配…</text>
        <text v-else class="cta-text">🍽 看看今天吃啥</text>
      </view>
    </view>

    <!-- 骨架屏 -->
    <view v-if="dailyStore.loading" class="skeleton-list">
      <view v-for="i in 3" :key="i" class="skeleton-card" />
    </view>

    <!-- 推荐结果 -->
    <view v-else-if="foods.length" class="result">
      <view class="result-head">
        <text class="result-title">为你推荐</text>
        <text class="result-tip">点击理由可展开</text>
      </view>
      <view class="food-list">
        <FoodCard
          v-for="food in foods"
          :key="food.id"
          :food="food"
          :chosen="isChosen(food.id)"
          @choose="onChoose"
        />
      </view>
    </view>

    <!-- 空状态 -->
    <view v-else class="empty">
      <text class="empty-emoji">🍚</text>
      <text class="empty-text">点击上方按钮，让算法给你搭配 3 道菜</text>
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
import type { FoodWithReason, Mood, ActivityLevel } from '@/types/api'

const dailyStore = useDailyStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const { getLocation } = useLocation()
const badgeRef = ref<InstanceType<typeof WeatherBadge> | null>(null)

const MOOD_EMOJI: Record<Mood, string> = { happy: '😄', neutral: '😌', tired: '😪', stressed: '😣', anxious: '😰' }
const ACTIVITY_EMOJI: Record<ActivityLevel, string> = { light: '🚶', normal: '🚶‍♂️', high: '🏃' }

const foods = computed<FoodWithReason[]>(() => dailyStore.recommendation?.foods || [])

const selectedFoodName = computed(() => {
  if (!dailyStore.todayLog || dailyStore.todayLog.chosenFoodIds.length === 0) return ''
  const chosenId = dailyStore.todayLog.chosenFoodIds[0]
  const f = foods.value.find((x) => x.id === chosenId)
  return f ? f.name : ''
})

function isChosen(foodId: number): boolean {
  return (dailyStore.todayLog?.chosenFoodIds || []).includes(foodId)
}

async function onRecommend() {
  if (!userStore.isLoggedIn) {
    uni.navigateTo({ url: '/pages/auth/auth' })
    return
  }
  let coords: Coords | null = null
  try {
    coords = await getLocation()
  } catch {
    // 位置拒绝 → 后端 fallback
  }
  try {
    await dailyStore.fetchRecommend(coords?.lat, coords?.lng)
    if (coords) badgeRef.value?.refreshWeather?.()
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
  if (userStore.isLoggedIn) {
    dailyStore.fetchTodayLog()
    favoriteStore.fetchList()
  }
  setTimeout(() => {
    badgeRef.value?.refreshWeather?.()
  }, 100)
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: $bg;
  padding: 24rpx 32rpx 60rpx;
  box-sizing: border-box;
}

/* ---- 英雄区 ---- */
.hero {
  display: flex;
  align-items: center;
  gap: 24rpx;
  padding: 40rpx 8rpx 28rpx;
}

.hero-avatar {
  width: 108rpx;
  height: 108rpx;
  border-radius: 32rpx;
  box-shadow: $shadow-card;
}

.hero-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.hero-title {
  font-size: 52rpx;
  font-weight: 700;
  color: $ink;
  letter-spacing: 2rpx;
}

.hero-sub {
  font-size: 24rpx;
  color: $ink-2;
}

.badge {
  align-self: flex-start;
  margin-top: 8rpx;
}

/* ---- 今日已选横幅 ---- */
.chosen-banner {
  display: flex;
  align-items: center;
  gap: 14rpx;
  background: $fresh-light;
  border: 1rpx solid #bfe8c8;
  border-radius: $radius-md;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}

.chosen-mark {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: $fresh;
  color: #fff;
  font-size: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.chosen-text {
  flex: 1;
  font-size: 26rpx;
  color: #1d6e2e;
  font-weight: 600;
}

.fav-link {
  font-size: 24rpx;
  color: $fresh;
}

/* ---- 输入面板 ---- */
.panel {
  background: $card;
  border-radius: $radius-lg;
  padding: 32rpx;
  box-shadow: $shadow-card;
  margin-bottom: 28rpx;
}

.panel-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 24rpx;

  &:last-of-type {
    margin-bottom: 32rpx;
  }
}

.panel-label {
  font-size: 26rpx;
  color: $ink-2;
  width: 96rpx;
  flex-shrink: 0;
  font-weight: 600;
}

.chip-row {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  flex: 1;
}

.chip {
  font-size: 24rpx;
  color: $ink-2;
  background: $bg;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  padding: 10rpx 22rpx;
  transition: all 0.2s;
}

.chip-on {
  color: $brand-dark;
  background: $brand-light;
  border-color: $brand-soft;
  font-weight: 600;
}

/* ---- 主 CTA ---- */
.cta {
  background: $grad-brand;
  border-radius: 999rpx;
  padding: 30rpx 0;
  text-align: center;
  box-shadow: $shadow-cta;
}

.cta-loading {
  opacity: 0.75;
}

.cta-text {
  color: #fff;
  font-size: 32rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

/* ---- 骨架屏 ---- */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.skeleton-card {
  height: 240rpx;
  background: linear-gradient(135deg, #f0e9e0 25%, #faf6f1 50%, #f0e9e0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: $radius-lg;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ---- 推荐结果 ---- */
.result {
  margin-top: 8rpx;
}

.result-head {
  display: flex;
  align-items: baseline;
  gap: 16rpx;
  margin-bottom: 20rpx;
  padding: 0 8rpx;
}

.result-title {
  font-size: 32rpx;
  font-weight: 700;
  color: $ink;
}

.result-tip {
  font-size: 22rpx;
  color: $ink-3;
}

.food-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

/* ---- 空状态 ---- */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 100rpx 0;
}

.empty-emoji {
  font-size: 88rpx;
}

.empty-text {
  font-size: 26rpx;
  color: $ink-3;
}
</style>