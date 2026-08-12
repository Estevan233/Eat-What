<template>
  <view class="plate-card">
    <view class="plate-head">
      <view>
        <text class="eyebrow">今日完整餐</text>
        <text class="headline">一主菜 · 一蔬菜 · 一主食</text>
      </view>
      <view class="time-pill"><text>⏱ {{ meal.estimatedTimeMin }} 分钟</text></view>
    </view>

    <view class="slots">
      <MealSlotRow
        v-for="item in orderedItems"
        :key="item.mealRole"
        :item="item"
        @open-recipe="emit('openRecipe', $event)"
      />
    </view>

    <NutritionSummary :nutrition="meal.totalNutrition" />
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

const props = withDefaults(defineProps<{ meal: MealSnapshot; readonly?: boolean }>(), {
  readonly: false,
})
const emit = defineEmits<{
  openRecipe: [item: MealItem]
  choose: []
}>()
const order: MealRole[] = ['main', 'vegetable', 'staple']
const orderedItems = computed(() => [...props.meal.items].sort(
  (left, right) => order.indexOf(left.mealRole) - order.indexOf(right.mealRole),
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
