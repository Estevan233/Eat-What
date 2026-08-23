<template>
  <view class="card" :class="{ 'card-chosen': chosen }">
    <!-- 左侧色条 -->
    <view class="accent-bar" :class="`bar-${food.nature}`" />

    <view class="card-body">
      <!-- 头部：菜名 + 收藏 -->
      <view class="head">
        <text class="name">{{ food.name }}</text>
        <text class="fav-btn" :class="{ 'fav-on': isFav }" @click="onToggleFavorite">
          {{ isFav ? '♥' : '♡' }}
        </text>
      </view>

      <!-- 元信息 -->
      <view class="meta-row">
        <text class="meta-chip chip-cat">{{ food.category }}</text>
        <text class="meta-chip">{{ food.cookingMethod }}</text>
        <text v-if="calories" class="meta-chip chip-cal">🔥 {{ calories }}千卡</text>
        <text v-for="tag in tags" :key="tag" class="meta-chip chip-tag">{{ tag }}</text>
      </view>

      <!-- 推荐理由 -->
      <view v-if="expanding" class="reason-box">
        <text class="reason-label">为什么推荐</text>
        <text class="reason-text">{{ food.reason }}</text>
      </view>
      <view v-else class="reason-line" @click="expanding = true">
        <text class="reason-ellipsis">💡 {{ food.reason }}</text>
      </view>

      <!-- 底部：分数 + 选择 -->
      <view class="footer">
        <view class="score">
          <text class="score-num">{{ Math.round(food.score) }}</text>
          <text class="score-unit">分</text>
        </view>
        <text class="choose-btn" :class="{ 'chosen-btn': chosen }" @click="onChoose">
          {{ chosen ? '已选 ✓' : '就吃这个' }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useFavoriteStore } from '@/stores/favorite'
import type { FoodWithReason } from '@/types/api'

const props = defineProps<{
  food: FoodWithReason
  chosen?: boolean
}>()

const emits = defineEmits<{
  choose: [food: FoodWithReason]
}>()

const favoriteStore = useFavoriteStore()
const isFav = computed(() => favoriteStore.isFavorited(props.food.id))
const expanding = ref(false)

const calories = computed(() => {
  const c = props.food.caloriesKcalPer100g
  return c !== undefined ? Math.round(c) : null
})

const tags = computed(() => props.food.tags.slice(0, 3))

function onChoose() {
  if (props.chosen) return
  emits('choose', props.food)
}

async function onToggleFavorite() {
  try {
    await favoriteStore.toggle(props.food.id)
  } catch {
    // toast 已由 request 层显示
  }
}
</script>

<style lang="scss" scoped>
.card {
  position: relative;
  display: flex;
  background: $card;
  border-radius: $radius-lg;
  overflow: hidden;
  box-shadow: $shadow-card;
  border: 1rpx solid $line;
}

.card-chosen {
  border-color: $fresh-light;
}

/* 左侧性味色条 */
.accent-bar {
  width: 10rpx;
  flex-shrink: 0;
}

.bar-cold, .bar-cool { background: $cold; }
.bar-neutral { background: $ink-3; }
.bar-warm, .bar-hot { background: $brand; }

.card-body {
  flex: 1;
  padding: 28rpx 28rpx 24rpx;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14rpx;
}

.name {
  font-size: 32rpx;
  font-weight: 700;
  color: $ink;
}

.fav-btn {
  font-size: 40rpx;
  color: $disabled;
  padding: 0 8rpx;
  transition: all 0.2s;
}

.fav-on {
  color: $danger;
  transform: scale(1.1);
}

/* 元信息 chips */
.meta-row {
  display: flex;
  gap: 10rpx;
  flex-wrap: wrap;
  margin-bottom: 16rpx;
}

.meta-chip {
  font-size: 20rpx;
  color: $ink-2;
  background: $bg;
  border-radius: 8rpx;
  padding: 4rpx 14rpx;
}

.chip-cat {
  color: $brand-dark;
  background: $brand-light;
  font-weight: 600;
}

.chip-cal {
  color: $warning;
  background: $warning-light;
}

.chip-tag {
  color: $fresh;
  background: $fresh-light;
}

/* 理由 */
.reason-line {
  margin-bottom: 18rpx;
}

.reason-ellipsis {
  font-size: 24rpx;
  color: $ink-2;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.reason-box {
  background: $brand-light;
  border-radius: $radius-sm;
  padding: 16rpx 20rpx;
  margin-bottom: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.reason-label {
  font-size: 20rpx;
  color: $brand;
  font-weight: 700;
}

.reason-text {
  font-size: 24rpx;
  color: $brand-dark;
  line-height: 1.6;
}

/* 底部 */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score {
  display: flex;
  align-items: baseline;
  gap: 2rpx;
}

.score-num {
  font-size: 40rpx;
  font-weight: 800;
  color: $brand;
}

.score-unit {
  font-size: 20rpx;
  color: $ink-3;
}

.choose-btn {
  font-size: 26rpx;
  color: #fff;
  background: $grad-brand;
  border-radius: 999rpx;
  padding: 14rpx 44rpx;
  font-weight: 600;
  box-shadow: $shadow-cta;
}

.chosen-btn {
  background: $disabled;
  box-shadow: none;
}
</style>