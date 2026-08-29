<template>
  <view class="page">
    <view v-if="loading" class="state"><text>菜谱加载中…</text></view>
    <view v-else-if="error" class="state error-state">
      <text>{{ error }}</text>
      <button class="retry" @click="loadRecipe">重试</button>
    </view>
    <template v-else-if="recipe">
      <view class="hero">
        <view class="hero-icon" :class="`hero-${recipe.mealRole}`">{{ roleIcon[recipe.mealRole] }}</view>
        <view class="hero-copy">
          <text class="role">{{ roleLabel[recipe.mealRole] }}</text>
          <text class="title">{{ recipe.foodName }}</text>
          <text class="meta">{{ recipe.servings }} 人份 · 备菜 {{ recipe.prepTimeMin }} 分钟 · 烹饪 {{ recipe.cookTimeMin }} 分钟</text>
        </view>
      </view>

      <NutritionSummary :nutrition="recipe.nutritionPerServing" />
      <text class="estimate-note">营养数值为每份估算，实际结果会随食材品牌与用量变化。</text>

      <view class="section">
        <view class="section-head"><text class="section-title">食材清单</text><text class="difficulty">{{ difficultyLabel }}</text></view>
        <view class="ingredient-list">
          <view v-for="(item, index) in recipe.ingredients" :key="`${item.name}-${index}`" class="ingredient">
            <text class="ingredient-name">{{ item.name }}<text v-if="item.optional" class="optional">（可选）</text></text>
            <text class="ingredient-amount">{{ ingredientAmount(item.amount, item.unit) }}</text>
          </view>
        </view>
      </view>

      <view class="section">
        <text class="section-title">做法</text>
        <view class="step-list">
          <view v-for="(step, index) in recipe.steps" :key="index" class="step">
            <text class="step-number">{{ index + 1 }}</text>
            <text class="step-copy">{{ step }}</text>
          </view>
        </view>
      </view>

      <view class="basis">
        <text class="basis-title">估算说明</text>
        <text class="basis-copy">{{ recipe.nutritionBasis }}</text>
        <button v-if="safeSourceUrl" class="source" @click="copySource">复制参考来源</button>
      </view>

      <button class="favorite" @click="toggleFavorite">
        {{ favorited ? '♥ 已收藏' : '♡ 收藏这道菜' }}
      </button>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import NutritionSummary from '@/components/NutritionSummary.vue'
import { getRecipe } from '@/api/recipe'
import { useFavoriteStore } from '@/stores/favorite'
import type { MealRole, RecipeRead } from '@/types/api'

const favoriteStore = useFavoriteStore()
const recipe = ref<RecipeRead | null>(null)
const foodId = ref(0)
const loading = ref(true)
const error = ref('')
const roleLabel: Record<MealRole, string> = { main: '主菜', vegetable: '蔬菜', staple: '主食' }
const roleIcon: Record<MealRole, string> = { main: '🥘', vegetable: '🥬', staple: '🍚' }
const difficultyLabels: Record<string, string> = { easy: '简单', medium: '适中', hard: '较难' }
const favorited = computed(() => favoriteStore.isFavorited(foodId.value))
const difficultyLabel = computed(() => difficultyLabels[recipe.value?.difficulty || ''] || '家常难度')
const safeSourceUrl = computed(() => {
  const value = recipe.value?.sourceUrl
  return value?.startsWith('https://') ? value : ''
})

onLoad((query) => {
  foodId.value = Number(query?.foodId || 0)
  if (!Number.isInteger(foodId.value) || foodId.value <= 0) {
    loading.value = false
    error.value = '菜品参数无效'
    return
  }
  loadRecipe()
  favoriteStore.fetchList().catch(() => undefined)
})

async function loadRecipe(): Promise<void> {
  if (!foodId.value) return
  loading.value = true
  error.value = ''
  try {
    recipe.value = await getRecipe(foodId.value)
    uni.setNavigationBarTitle({ title: recipe.value.foodName })
  } catch {
    error.value = '菜谱暂时没有加载出来，请稍后重试'
  } finally {
    loading.value = false
  }
}

function ingredientAmount(amount: number | null | undefined, unit: string): string {
  if (amount === null || amount === undefined) return unit
  return `${Number.isInteger(amount) ? amount : amount.toFixed(1)} ${unit}`
}

async function toggleFavorite(): Promise<void> {
  try {
    const active = await favoriteStore.toggle(foodId.value)
    uni.showToast({ title: active ? '已收藏' : '已取消收藏', icon: 'none' })
  } catch {
    // request 层已展示可操作错误。
  }
}

function copySource(): void {
  if (!safeSourceUrl.value) return
  uni.setClipboardData({ data: safeSourceUrl.value })
}

onShareAppMessage(() => {
  return {
    title: recipe.value?.foodName ? `饭卜卜 · ${recipe.value.foodName}` : '饭卜卜 · 菜谱详情',
    path: `/pages/recipe/recipe?foodId=${foodId.value}`,
  }
})

onShareTimeline(() => {
  return {
    title: recipe.value?.foodName ? `饭卜卜 · ${recipe.value.foodName}` : '饭卜卜 · 菜谱详情',
  }
})

</script>

<style lang="scss" scoped>
.page { min-height: 100vh; padding: 30rpx 32rpx 80rpx; box-sizing: border-box; background: $bg; }
.state { min-height: 60vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24rpx; color: $ink-2; font-size: 27rpx; }
.error-state { color: #a14325; }
.retry { min-width: 200rpx; height: 88rpx; line-height: 88rpx; border-radius: 999rpx; background: $brand; color: #fff; font-size: 26rpx; }
.retry::after { border: none; }
.hero { display: flex; align-items: center; gap: 24rpx; padding: 28rpx 4rpx 32rpx; }
.hero-icon { width: 124rpx; height: 124rpx; flex: 0 0 124rpx; border-radius: 36rpx; display: flex; align-items: center; justify-content: center; font-size: 60rpx; }
.hero-main { background: linear-gradient(145deg, #fff0e4, #ffd9be); }
.hero-vegetable { background: linear-gradient(145deg, #edf9ef, #ccefd4); }
.hero-staple { background: linear-gradient(145deg, #fff8dd, #f8e7aa); }
.hero-copy { min-width: 0; display: flex; flex-direction: column; gap: 8rpx; }
.role { align-self: flex-start; color: $brand-dark; background: $brand-light; padding: 4rpx 14rpx; border-radius: 999rpx; font-size: 20rpx; }
.title { color: $ink; font-size: 42rpx; font-weight: 800; }
.meta { color: $ink-2; font-size: 22rpx; line-height: 1.5; }
.estimate-note { display: block; color: $ink-3; font-size: 20rpx; line-height: 1.5; padding: 12rpx 8rpx 2rpx; }
.section { margin-top: 28rpx; padding: 30rpx; border-radius: 30rpx; background: $card; border: 1rpx solid $line; box-shadow: $shadow-card; }
.section-head { display: flex; align-items: center; justify-content: space-between; }
.section-title { color: $ink; font-size: 31rpx; font-weight: 750; }
.difficulty { color: $fresh; background: $fresh-light; border-radius: 999rpx; padding: 6rpx 16rpx; font-size: 21rpx; }
.ingredient-list { margin-top: 18rpx; }
.ingredient { min-height: 70rpx; display: flex; align-items: center; justify-content: space-between; gap: 20rpx; border-bottom: 1rpx solid $line; }
.ingredient:last-child { border-bottom: none; }
.ingredient-name { color: $ink; font-size: 25rpx; }
.optional { color: $ink-3; font-size: 21rpx; }
.ingredient-amount { color: $brand-dark; font-size: 24rpx; font-weight: 650; }
.step-list { margin-top: 24rpx; display: flex; flex-direction: column; gap: 22rpx; }
.step { display: flex; align-items: flex-start; gap: 18rpx; }
.step-number { width: 46rpx; height: 46rpx; flex: 0 0 46rpx; border-radius: 50%; background: $brand-light; color: $brand-dark; display: flex; align-items: center; justify-content: center; font-size: 23rpx; font-weight: 750; }
.step-copy { flex: 1; color: $ink; font-size: 26rpx; line-height: 1.75; }
.basis { margin-top: 24rpx; padding: 24rpx 26rpx; border-radius: 24rpx; background: #f5f0e9; display: flex; flex-direction: column; gap: 8rpx; }
.basis-title { color: $ink-2; font-size: 23rpx; font-weight: 700; }
.basis-copy { color: $ink-3; font-size: 21rpx; line-height: 1.6; }
.source { align-self: flex-start; margin: 8rpx 0 0; padding: 0; background: transparent; color: $brand; font-size: 22rpx; line-height: 1.8; }
.source::after { border: none; }
.favorite { height: 96rpx; line-height: 96rpx; margin-top: 30rpx; border-radius: 999rpx; color: #fff; background: $grad-brand; font-size: 29rpx; font-weight: 750; box-shadow: $shadow-cta; }
.favorite::after { border: none; }
</style>
