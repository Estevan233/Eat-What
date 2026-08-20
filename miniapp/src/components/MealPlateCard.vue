<template>
  <view class="plate-card">
    <view class="plate-head">
      <view>
        <text class="eyebrow">今日完整餐</text>
        <text class="headline">{{ roleHeadline }}</text>
      </view>
      <view class="time-pill"><text>⏱ {{ meal.estimatedTimeMin }} 分钟</text></view>
    </view>

    <view class="slots">
      <MealSlotRow
        v-for="item in orderedItems"
        :key="item.foodId"
        :item="item"
        @open-recipe="emit('openRecipe', $event)"
      />
    </view>

    <NutritionSummary :nutrition="meal.totalNutrition" />
    <text v-if="partySize > 1" class="table-energy">
      人均按每份估算 · 全桌约 {{ wholeTableEnergy }} kcal
    </text>
    <text class="meal-reason">{{ meal.reason }}</text>
    <button class="choose" :disabled="readonly" @click="emit('choose')">
      {{ readonly ? '刷新后可确认' : '就吃这套' }}
    </button>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MealSlotRow from './MealSlotRow.vue'
import NutritionSummary from './NutritionSummary.vue'
import type { MealItem, MealRole, MealSnapshot } from '@/types/api'

const props = withDefaults(defineProps<{
  meal: MealSnapshot
  readonly?: boolean
  partySize?: number
}>(), {
  readonly: false,
  partySize: 1,
})
const emit = defineEmits<{
  openRecipe: [item: MealItem]
  choose: []
}>()
const order: MealRole[] = ['main', 'vegetable', 'staple']
const orderedItems = computed(() => [...props.meal.items].sort(
  (left, right) => order.indexOf(left.mealRole) - order.indexOf(right.mealRole),
))
const countNames = ['', '一', '两', '三', '四', '五', '六']
const roleNames: Record<MealRole, string> = {
  main: '主菜',
  vegetable: '蔬菜',
  staple: '主食',
}
const roleHeadline = computed(() => order
  .map((role) => {
    const count = props.meal.items.filter((item) => item.mealRole === role).length
    return count > 0 ? (countNames[count] || String(count)) + roleNames[role] : ''
  })
  .filter(Boolean)
  .join(' · '))
const wholeTableEnergy = computed(() => Math.round(
  props.meal.totalNutrition.energyKcal * props.partySize,
))
</script>

<style lang="scss" scoped>
.plate-card { background: $card; border-radius: 36rpx; padding: 30rpx; border: 1rpx solid $line; box-shadow: 0 18rpx 52rpx rgba(94, 57, 28, 0.09); }
.plate-head { display: flex; justify-content: space-between; gap: 20rpx; align-items: center; margin-bottom: 8rpx; }
.plate-head > view:first-child { display: flex; flex-direction: column; gap: 5rpx; }
.eyebrow { color: $brand; font-size: 22rpx; font-weight: 700; letter-spacing: 2rpx; }
.headline { color: $ink; font-size: 32rpx; font-weight: 750; }
.time-pill { flex: 0 0 auto; padding: 10rpx 16rpx; border-radius: 999rpx; background: $bg; color: $ink-2; font-size: 21rpx; }
.slots { margin: 8rpx 0 22rpx; }
.table-energy { display: block; padding: 12rpx 6rpx 0; color: -3; font-size: 20rpx; }
.meal-reason { display: block; color: $ink-2; font-size: 23rpx; line-height: 1.65; padding: 20rpx 6rpx 6rpx; }
.choose { height: 96rpx; line-height: 96rpx; margin-top: 18rpx; border: none; border-radius: 999rpx; color: #fff; background: $grad-brand; font-size: 30rpx; font-weight: 750; box-shadow: $shadow-cta; }
.choose::after { border: none; }
.choose[disabled] { color: #fff; opacity: .48; }
@media (max-width: 340px) {
  .plate-card { padding: 24rpx; }
  .plate-head { align-items: flex-start; }
  .headline { font-size: 29rpx; }
  .time-pill { padding: 8rpx 12rpx; }
}
</style>
