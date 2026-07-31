<template>
  <view class="card">
    <view class="card-header">
      <text class="name">{{ food.name }}</text>
      <view class="actions">
        <text
          class="fav-btn"
          :class="{ 'fav-active': isFav }"
          @click="onToggleFavorite"
        >{{ isFav ? '♥' : '♡' }}</text>
      </view>
    </view>

    <view class="info-row">
      <text v-if="calories" class="info-item">×100g {{ calories }}千卡</text>
      <text class="info-item">{{ food.cookingMethod }}</text>
      <text v-for="tag in tags" :key="tag" class="tag-chip">{{ tag }}</text>
    </view>

    <view v-if="expanding" class="reason-box">
      <text class="reason-text">{{ food.reason }}</text>
    </view>
    <text v-else class="reason-line" @click="expanding = true">
      <text class="reason-ellipsis">{{ food.reason }}</text>
    </text>

    <view class="footer">
      <text class="score-badge">{{ Math.round(food.score) }}分</text>
      <text
        class="choose-btn"
        :class="{ 'chosen-btn': chosen }"
        @click="onChoose"
      >{{ chosen ? '已选 ✓' : '就吃这个' }}</text>
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
  flex: 1;
  background: #f9fafb;
  border: 1rpx solid #e5e7eb;
  border-radius: 18rpx;
  padding: 32rpx;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.name {
  font-size: 30rpx;
  font-weight: 600;
  color: #1f2937;
}

.actions {
  display: flex;
}

.fav-btn {
  font-size: 38rpx;
  color: #cbd5e1;
  padding: 4rpx 8rpx;
}

.fav-active {
  color: #ef4444;
}

.info-row {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  margin-bottom: 16rpx;
}

.info-item {
  font-size: 24rpx;
  color: #6b7280;
}

.tag-chip {
  font-size: 22rpx;
  color: #4b5563;
  background: #e0e7ff;
  border-radius: 8rpx;
  padding: 4rpx 12rpx;
}

.reason-line {
  display: block;
  font-size: 26rpx;
  color: #4338ca;
  line-height: 1.4;
  margin-bottom: 12rpx;
}

.reason-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.reason-box {
  background: #eff6ff;
  border-radius: 12rpx;
  padding: 14rpx 18rpx;
  margin-bottom: 12rpx;
}

.reason-text {
  font-size: 26rpx;
  color: #4338ca;
  line-height: 1.4;
}

.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-badge {
  font-size: 22rpx;
  color: #94a3b8;
}

.choose-btn {
  font-size: 26rpx;
  color: #ffffff;
  background: #2563eb;
  border-radius: 32rpx;
  padding: 12rpx 32rpx;
}

.chosen-btn {
  background: #94a3b8;
}
</style>