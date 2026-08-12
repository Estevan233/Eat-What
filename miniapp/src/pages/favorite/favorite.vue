<template>
  <view class="page">
    <view class="heading">
      <text class="page-title">我的收藏</text>
      <text class="page-sub">点开查看食材用量和做法</text>
    </view>

    <view v-if="loading" class="hint"><text>加载中…</text></view>
    <view v-else-if="favorites.length === 0" class="hint">
      <text class="hint-emoji">♡</text>
      <text>还没有收藏的菜，先去挑一套餐吧。</text>
    </view>
    <view v-else class="list">
      <view
        v-for="food in favorites"
        :key="food.id"
        class="fav-item"
        :class="{ tappable: food.recipeReady }"
        @click="openRecipe(food.id, food.recipeReady)"
      >
        <view class="visual">{{ roleIcon(food.mealRole) }}</view>
        <view class="fav-info">
          <text class="fav-name">{{ food.name }}</text>
          <text class="fav-meta">{{ food.category }} · {{ food.cookingMethod }}</text>
          <text v-if="recipeEnergy[food.id]" class="fav-cal">约 {{ recipeEnergy[food.id] }} kcal / 份</text>
          <text v-else-if="food.caloriesKcalPer100g" class="fav-cal fallback-cal">
            {{ Math.round(food.caloriesKcalPer100g) }} kcal / 100g（原料参考）
          </text>
          <text v-if="food.recipeReady" class="recipe-link">查看菜谱 ›</text>
        </view>
        <button class="unfav-btn" @click.stop="onUndo(food.id)">取消</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getRecipe } from '@/api/recipe'
import { useFavoriteStore } from '@/stores/favorite'
import type { MealRole } from '@/types/api'

const favoriteStore = useFavoriteStore()
const favorites = computed(() => favoriteStore.favorites)
const loading = computed(() => favoriteStore.loading)
const recipeEnergy = ref<Record<number, number>>({})
const icons: Record<MealRole, string> = { main: '🥘', vegetable: '🥬', staple: '🍚' }

onShow(async () => {
  try {
    const items = await favoriteStore.fetchList(true)
    await Promise.all(items.filter((item) => item.recipeReady).map(async (item) => {
      try {
        const recipe = await getRecipe(item.id)
        recipeEnergy.value[item.id] = Math.round(recipe.nutritionPerServing.energyKcal)
      } catch {
        // 单道菜谱加载失败仍保留收藏卡片与 100g 参考值。
      }
    }))
  } catch {
    // request 层处理错误。
  }
})

function roleIcon(role?: MealRole | null): string {
  return role ? icons[role] : '🍽'
}

function openRecipe(foodId: number, ready?: boolean): void {
  if (!ready) {
    uni.showToast({ title: '这道菜的结构化菜谱还在整理', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/recipe/recipe?foodId=${foodId}` })
}

async function onUndo(foodId: number): Promise<void> {
  try {
    await favoriteStore.toggle(foodId)
    await favoriteStore.fetchList(true)
    uni.showToast({ title: '已取消收藏', icon: 'none' })
  } catch {
    // request 层处理错误。
  }
}
</script>

<style lang="scss" scoped>
.page { min-height: 100vh; padding: 38rpx 32rpx 70rpx; box-sizing: border-box; background: $bg; }
.heading { display: flex; flex-direction: column; gap: 6rpx; margin-bottom: 28rpx; }
.page-title { color: $ink; font-size: 42rpx; font-weight: 800; }
.page-sub { color: $ink-3; font-size: 23rpx; }
.hint { min-height: 54vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14rpx; color: $ink-3; font-size: 26rpx; }
.hint-emoji { font-size: 72rpx; color: $brand-soft; }
.list { display: flex; flex-direction: column; gap: 18rpx; }
.fav-item { display: flex; align-items: center; gap: 20rpx; min-height: 146rpx; padding: 24rpx; border: 1rpx solid $line; border-radius: 28rpx; background: $card; box-shadow: $shadow-card; }
.tappable:active { background: #fffaf6; }
.visual { width: 88rpx; height: 88rpx; flex: 0 0 88rpx; display: flex; align-items: center; justify-content: center; border-radius: 25rpx; background: $brand-light; font-size: 42rpx; }
.fav-info { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 6rpx; }
.fav-name { color: $ink; font-size: 29rpx; font-weight: 700; }
.fav-meta, .fav-cal { color: $ink-2; font-size: 21rpx; }
.fallback-cal { color: $ink-3; }
.recipe-link { color: $brand; font-size: 21rpx; font-weight: 650; }
.unfav-btn { min-width: 96rpx; height: 72rpx; line-height: 72rpx; margin: 0; padding: 0 16rpx; border-radius: 999rpx; color: #b42318; background: #fff1ef; font-size: 22rpx; }
.unfav-btn::after { border: none; }
</style>
