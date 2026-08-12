<template>
  <view class="page">
    <view class="hero">
      <image class="hero-avatar" src="/static/brand-avatar.png" mode="aspectFill" />
      <view class="hero-text">
        <text class="hero-title">今天吃啥</text>
        <text class="hero-sub">天气只是小参考，均衡与口味才是正餐</text>
      </view>
    </view>
    <WeatherBadge ref="badgeRef" class="context-badge" />

    <view v-if="chosenMealNames" class="chosen-banner">
      <text class="chosen-mark">✓</text>
      <view class="chosen-copy">
        <text class="chosen-title">今天就吃这套</text>
        <text class="chosen-text">{{ chosenMealNames }}</text>
      </view>
      <navigator url="/pages/history/history" class="history-link">历史 ›</navigator>
    </view>

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
      <button class="cta" :disabled="dailyStore.loading" @click="onRecommend">
        {{ dailyStore.loading ? '正在为你搭配…' : '🍽 换一套完整餐' }}
      </button>
    </view>

    <view v-if="pageError" class="error-banner">
      <text class="error-title">这次没有拿到新推荐</text>
      <text class="error-copy">{{ pageError }}</text>
      <text v-if="dailyStore.lastRequestId" class="request-id">请求编号：{{ dailyStore.lastRequestId }}</text>
    </view>

    <view v-if="dailyStore.loading" class="skeleton-card" />

    <view v-else-if="dailyStore.currentMeal" class="result">
      <view v-if="dailyStore.stale || dailyStore.offline" class="cache-banner">
        <text class="cache-title">{{ dailyStore.offline ? '当前离线 · 展示上次推荐' : '上次推荐' }}</text>
        <text class="cache-copy">可以查看菜谱；刷新成功前不能换菜或确认。</text>
      </view>

      <MealPlateCard
        :meal="dailyStore.currentMeal"
        :readonly="dailyStore.stale || dailyStore.offline"
        @open-recipe="openRecipe"
        @choose="chooseCurrentMeal"
      />

      <view v-if="dailyStore.availableSubstitutions.length" class="substitutions">
        <view class="section-head">
          <text class="section-title">想换个口味？</text>
          <text class="section-tip">热量尽量控制在相近范围</text>
        </view>
        <MealSubstitution
          v-for="item in dailyStore.availableSubstitutions"
          :key="`${item.targetRole}-${item.replacement.foodId}`"
          :substitution="item"
          :readonly="dailyStore.stale || dailyStore.offline"
          @apply="dailyStore.applySubstitution(item)"
        />
      </view>
      <text v-else-if="dailyStore.serverRecommendation?.substitutionNotice" class="notice">
        {{ dailyStore.serverRecommendation.substitutionNotice }}
      </text>
    </view>

    <view v-else class="empty">
      <text class="empty-emoji">🍚</text>
      <text class="empty-title">还没有今天的完整餐</text>
      <text class="empty-text">点击上方按钮，会搭配主菜、蔬菜和主食，并标出每份估算能量。</text>
      <button v-if="pageError" class="empty-retry" @click="onRecommend">重新获取</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import MealPlateCard from '@/components/MealPlateCard.vue'
import MealSubstitution from '@/components/MealSubstitution.vue'
import WeatherBadge from '@/components/WeatherBadge.vue'
import { useDailyStore } from '@/stores/daily'
import { useFavoriteStore } from '@/stores/favorite'
import { useUserStore } from '@/stores/user'
import { useLocation, type Coords } from '@/composables/useLocation'
import { MOOD_LABELS, MOOD_LIST, ACTIVITY_LABELS, ACTIVITY_LIST } from '@/constants/daily'
import { ApiError } from '@/types/api'
import type { ActivityLevel, MealItem, Mood } from '@/types/api'

const dailyStore = useDailyStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const { getLocation } = useLocation()
const badgeRef = ref<InstanceType<typeof WeatherBadge> | null>(null)
const pageError = ref('')

const MOOD_EMOJI: Record<Mood, string> = {
  happy: '😄', neutral: '😌', tired: '😪', stressed: '😣', anxious: '😰',
}
const ACTIVITY_EMOJI: Record<ActivityLevel, string> = {
  light: '🚶', normal: '🚶‍♂️', high: '🏃',
}
const chosenMealNames = computed(() => {
  const items = dailyStore.todayLog?.chosenMeal?.items
  if (items?.length) return items.map((item) => item.name).join(' · ')
  return ''
})

async function onRecommend(): Promise<void> {
  if (dailyStore.loading) return
  pageError.value = ''
  if (!userStore.isLoggedIn) {
    uni.navigateTo({ url: '/pages/auth/auth' })
    return
  }
  if (!userStore.hasProfile) {
    uni.showToast({ title: '请先填写健康档案', icon: 'none' })
    uni.switchTab({ url: '/pages/profile/profile' })
    return
  }
  let coords: Coords | null = null
  try {
    coords = await getLocation()
  } catch {
    // 拒绝定位仍使用后端通用天气，不阻断推荐。
  }
  try {
    await dailyStore.fetchRecommend(coords?.lat, coords?.lng)
    if (coords) badgeRef.value?.refreshWeather?.()
    uni.showToast({ title: dailyStore.offline ? '已展示上次推荐' : '完整餐已搭配', icon: 'none' })
  } catch (error) {
    const apiError = error instanceof ApiError ? error : null
    pageError.value = apiError?.code === 'SERVICE_CONFIG_ERROR'
      ? '云托管服务尚未正确配置，请把请求编号发给开发者。'
      : (apiError?.message || '请检查网络后重试。')
  }
}

function openRecipe(item: MealItem): void {
  uni.navigateTo({ url: `/pages/recipe/recipe?foodId=${item.foodId}` })
}

async function chooseCurrentMeal(): Promise<void> {
  try {
    await dailyStore.chooseCurrentMeal()
    uni.showToast({ title: '今天就吃这套', icon: 'success' })
  } catch {
    // request 层或禁用状态已经给出明确反馈。
  }
}

onShow(() => {
  if (userStore.isLoggedIn) {
    dailyStore.fetchTodayLog().catch(() => undefined)
    favoriteStore.fetchList().catch(() => undefined)
  }
  setTimeout(() => badgeRef.value?.refreshWeather?.(), 100)
})
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; background: $bg; padding: 22rpx 32rpx 70rpx; box-sizing: border-box; }
.hero { display: flex; align-items: center; gap: 20rpx; padding: 32rpx 6rpx 26rpx; }
.hero-avatar { width: 100rpx; height: 100rpx; flex: 0 0 100rpx; border-radius: 30rpx; box-shadow: $shadow-card; }
.hero-text { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 5rpx; }
.hero-title { color: $ink; font-size: 48rpx; font-weight: 800; letter-spacing: 1rpx; }
.hero-sub { color: $ink-2; font-size: 21rpx; line-height: 1.4; }
.context-badge { margin: 0 6rpx 22rpx; max-width: calc(100% - 12rpx); box-sizing: border-box; }
.chosen-banner { display: flex; align-items: center; gap: 14rpx; margin-bottom: 22rpx; padding: 20rpx 22rpx; border: 1rpx solid #bfe8c8; border-radius: $radius-md; background: $fresh-light; }
.chosen-mark { width: 42rpx; height: 42rpx; flex: 0 0 42rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; background: $fresh; font-size: 23rpx; font-weight: 800; }
.chosen-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 4rpx; }
.chosen-title { color: #1d6e2e; font-size: 24rpx; font-weight: 700; }
.chosen-text { color: #347b43; font-size: 21rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-link { color: $fresh; font-size: 22rpx; }
.panel { margin-bottom: 26rpx; padding: 28rpx; border-radius: $radius-lg; background: $card; box-shadow: $shadow-card; }
.panel-row { display: flex; align-items: flex-start; gap: 14rpx; margin-bottom: 22rpx; }
.panel-label { width: 88rpx; flex: 0 0 88rpx; padding-top: 10rpx; color: $ink-2; font-size: 24rpx; font-weight: 650; }
.chip-row { flex: 1; display: flex; flex-wrap: wrap; gap: 10rpx; }
.chip { padding: 9rpx 18rpx; border: 1rpx solid $line; border-radius: 999rpx; color: $ink-2; background: $bg; font-size: 22rpx; }
.chip-on { color: $brand-dark; border-color: $brand-soft; background: $brand-light; font-weight: 650; }
.cta { height: 94rpx; line-height: 94rpx; margin-top: 8rpx; border: none; border-radius: 999rpx; color: #fff; background: $grad-brand; box-shadow: $shadow-cta; font-size: 29rpx; font-weight: 750; }
.cta::after { border: none; }
.cta[disabled] { color: #fff; opacity: .65; }
.error-banner, .cache-banner { display: flex; flex-direction: column; gap: 6rpx; margin-bottom: 20rpx; padding: 20rpx 22rpx; border-radius: 20rpx; }
.error-banner { color: #8c351d; background: #fff0eb; border: 1rpx solid #ffd0c2; }
.cache-banner { color: #765315; background: #fff8df; border: 1rpx solid #f1df9e; }
.error-title, .cache-title { font-size: 24rpx; font-weight: 750; }
.error-copy, .cache-copy, .request-id { font-size: 21rpx; line-height: 1.5; }
.request-id { word-break: break-all; opacity: .75; }
.skeleton-card { height: 720rpx; border-radius: 36rpx; background: linear-gradient(100deg, #f0e9e0 20%, #faf6f1 50%, #f0e9e0 80%); background-size: 220% 100%; animation: shimmer 1.4s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.result { display: flex; flex-direction: column; gap: 22rpx; }
.substitutions { display: flex; flex-direction: column; gap: 12rpx; padding: 24rpx; border-radius: 28rpx; background: rgba(255, 255, 255, .72); border: 1rpx solid $line; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 20rpx; padding: 0 4rpx 8rpx; }
.section-title { color: $ink; font-size: 28rpx; font-weight: 750; }
.section-tip { color: $ink-3; font-size: 19rpx; text-align: right; }
.notice { padding: 18rpx 22rpx; border-radius: 20rpx; color: $ink-2; background: #fff; border: 1rpx solid $line; font-size: 22rpx; line-height: 1.55; }
.empty { min-height: 420rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14rpx; padding: 40rpx 24rpx; text-align: center; }
.empty-emoji { font-size: 78rpx; }
.empty-title { color: $ink; font-size: 29rpx; font-weight: 700; }
.empty-text { max-width: 560rpx; color: $ink-3; font-size: 23rpx; line-height: 1.65; }
.empty-retry { min-width: 220rpx; height: 88rpx; line-height: 88rpx; margin-top: 12rpx; border-radius: 999rpx; color: #fff; background: $brand; font-size: 25rpx; }
.empty-retry::after { border: none; }
@media (max-width: 340px) {
  .page { padding-left: 24rpx; padding-right: 24rpx; }
  .hero { gap: 14rpx; }
  .hero-avatar { width: 88rpx; height: 88rpx; flex-basis: 88rpx; }
  .hero-title { font-size: 42rpx; }
  .panel { padding: 24rpx; }
}
</style>
