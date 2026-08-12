<template>
  <view class="page">
    <view class="heading">
      <text class="page-title">历史记录</text>
      <text class="page-sub">保存的是当时的餐单快照，不会随菜谱更新而变化</text>
    </view>

    <view v-if="loading" class="hint"><text>加载中…</text></view>
    <view v-else-if="items.length === 0" class="hint"><text>还没有历史记录，先去搭配今天的一餐吧。</text></view>
    <view v-else class="list">
      <view v-for="log in items" :key="log.id" class="log-card">
        <view class="log-head">
          <text class="log-date">{{ log.logDate }}</text>
          <view class="context-tags">
            <text class="mood-tag">{{ moodLabel(log.mood) }}</text>
            <text v-if="log.weatherTag" class="weather-tag">{{ weatherLabel(log.weatherTag) }}</text>
          </view>
        </view>

        <template v-if="log.chosenMeal?.items?.length">
          <view class="meal-names">
            <view v-for="item in log.chosenMeal.items" :key="item.mealRole" class="meal-name">
              <text class="role-dot">{{ roleIcon[item.mealRole] }}</text>
              <text>{{ item.name }}</text>
            </view>
          </view>
          <view v-if="log.chosenTotalNutrition" class="nutrition-line">
            <text>约 {{ Math.round(log.chosenTotalNutrition.energyKcal) }} kcal / 份</text>
            <text>蛋白质 {{ format(log.chosenTotalNutrition.proteinG) }}g</text>
            <text>约 {{ log.chosenMeal.estimatedTimeMin }} 分钟</text>
          </view>
        </template>
        <view v-else class="legacy-row">
          <text v-if="log.chosenFoodIds.length">旧版记录：选择了 {{ log.chosenFoodIds.length }} 道</text>
          <text v-else>当天未确认餐单</text>
        </view>
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
import type { MealRole } from '@/types/api'

const dailyStore = useDailyStore()
const items = ref<DailyLogRead[]>([])
const loading = ref(false)
const roleIcon: Record<MealRole, string> = { main: '🥘', vegetable: '🥬', staple: '🍚' }

onShow(async () => {
  loading.value = true
  try {
    const response = await dailyStore.fetchHistory(30)
    if (response) items.value = response.items
  } catch {
    // request 层处理认证/配置错误。
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
function format(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; padding: 38rpx 32rpx 70rpx; box-sizing: border-box; background: $bg; }
.heading { display: flex; flex-direction: column; gap: 6rpx; margin-bottom: 28rpx; }
.page-title { color: $ink; font-size: 42rpx; font-weight: 800; }
.page-sub { color: $ink-3; font-size: 22rpx; line-height: 1.5; }
.hint { min-height: 54vh; display: flex; align-items: center; justify-content: center; color: $ink-3; font-size: 26rpx; text-align: center; }
.list { display: flex; flex-direction: column; gap: 20rpx; }
.log-card { padding: 26rpx; border: 1rpx solid $line; border-radius: 28rpx; background: $card; box-shadow: $shadow-card; }
.log-head { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding-bottom: 18rpx; border-bottom: 1rpx solid $line; }
.log-date { color: $ink; font-size: 28rpx; font-weight: 750; }
.context-tags { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8rpx; }
.mood-tag, .weather-tag { padding: 4rpx 11rpx; border-radius: 999rpx; font-size: 20rpx; }
.mood-tag { color: $brand-dark; background: $brand-light; }
.weather-tag { color: $ink-2; background: $bg; }
.meal-names { display: flex; flex-direction: column; gap: 12rpx; padding: 20rpx 0; }
.meal-name { display: flex; align-items: center; gap: 12rpx; color: $ink; font-size: 25rpx; font-weight: 600; }
.role-dot { font-size: 28rpx; }
.nutrition-line { display: flex; flex-wrap: wrap; gap: 10rpx 18rpx; padding: 16rpx 18rpx; border-radius: 18rpx; color: $ink-2; background: #fff7ef; font-size: 20rpx; }
.legacy-row { padding-top: 20rpx; color: $ink-3; font-size: 23rpx; }
</style>
