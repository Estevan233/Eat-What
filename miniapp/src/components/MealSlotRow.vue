<template>
  <view class="slot" @click="emit('openRecipe', item)">
    <view class="visual" :class="`visual-${item.mealRole}`">
      <text>{{ roleIcon[item.mealRole] }}</text>
    </view>
    <view class="body">
      <view class="title-line">
        <text class="role">{{ roleLabel[item.mealRole] }}</text>
        <text class="name">{{ item.name }}</text>
      </view>
      <text class="meta">约 {{ Math.round(item.nutritionPerServing.energyKcal) }} kcal/份 · {{ methodLabel(item.cookingMethod) }}</text>
      <text class="reason">{{ item.reason }}</text>
    </view>
    <text class="arrow">›</text>
  </view>
</template>

<script setup lang="ts">
import type { MealItem, MealRole } from '@/types/api'

defineProps<{ item: MealItem }>()
const emit = defineEmits<{ openRecipe: [item: MealItem] }>()

const roleLabel: Record<MealRole, string> = {
  main: '主菜',
  vegetable: '蔬菜',
  staple: '主食',
}
const roleIcon: Record<MealRole, string> = {
  main: '🥘',
  vegetable: '🥬',
  staple: '🍚',
}
const methods: Record<string, string> = {
  stir_fry: '炒', steam: '蒸', boil: '煮', soup: '汤', cold: '凉拌',
  blanch: '焯拌', braise: '炖', bake: '烤', pan_fry: '煎',
}
function methodLabel(value: string): string {
  return methods[value] || value
}
</script>

<style lang="scss" scoped>
.slot { display: flex; align-items: center; gap: 20rpx; min-height: 132rpx; padding: 20rpx 0; border-bottom: 1rpx solid $line; }
.slot:last-child { border-bottom: none; }
.visual { width: 92rpx; height: 92rpx; flex: 0 0 92rpx; border-radius: 26rpx; display: flex; align-items: center; justify-content: center; font-size: 44rpx; }
.visual-main { background: linear-gradient(145deg, #fff0e4, #ffd9be); }
.visual-vegetable { background: linear-gradient(145deg, #edf9ef, #ccefd4); }
.visual-staple { background: linear-gradient(145deg, #fff8dd, #f8e7aa); }
.body { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 7rpx; }
.title-line { display: flex; align-items: center; gap: 12rpx; min-width: 0; }
.role { flex: 0 0 auto; color: $brand-dark; background: $brand-light; border-radius: 999rpx; padding: 3rpx 12rpx; font-size: 20rpx; }
.name { color: $ink; font-size: 30rpx; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: $ink-2; font-size: 22rpx; }
.reason { color: $ink-3; font-size: 21rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.arrow { color: $ink-3; font-size: 42rpx; padding: 20rpx 0 20rpx 12rpx; }
</style>
