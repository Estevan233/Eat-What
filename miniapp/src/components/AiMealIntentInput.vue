<template>
  <view v-if="enabled && dailyStore.diningMode === 'cook'" class="ai-panel">
    <view class="ai-row">
      <input
        v-model="text"
        class="ai-input"
        :maxlength="200"
        placeholder="冰箱里有什么？几分钟？想怎么吃？"
        confirm-type="done"
        :disabled="parsing"
        @confirm="onParse"
      />
      <view class="ai-btn" :class="{ 'ai-btn-off': parsing || !canSubmit }" @click="onParse">
        <text class="ai-btn-text">{{ parsing ? '理解中…' : '帮我配' }}</text>
      </view>
    </view>

    <view v-if="intent" class="ai-tags">
      <view
        v-for="item in intent.availableIngredients"
        :key="`has-${item}`"
        class="ai-tag ai-tag-has"
        @click="removeAvailable(item)"
      >
        <text class="ai-tag-text">有 {{ item }} ✕</text>
      </view>
      <view
        v-for="item in intent.excludedIngredients"
        :key="`no-${item}`"
        class="ai-tag ai-tag-no"
        @click="removeExcluded(item)"
      >
        <text class="ai-tag-text">不要 {{ item }} ✕</text>
      </view>
      <view v-if="intent.maxTimeMinutes" class="ai-tag ai-tag-time" @click="clearTime">
        <text class="ai-tag-text">{{ intent.maxTimeMinutes }} 分钟内 ✕</text>
      </view>
      <view v-if="intent.goal" class="ai-tag ai-tag-goal" @click="clearGoal">
        <text class="ai-tag-text">{{ goalLabel }} ✕</text>
      </view>
      <view class="ai-tag ai-tag-clear" @click="onClear">
        <text class="ai-tag-text">清空 ✕</text>
      </view>
    </view>

    <text v-if="intent && intent.summary" class="ai-summary">{{ intent.summary }}</text>
    <text v-if="failed" class="ai-hint">没太理解，可以直接选下面的条件</text>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { extractMealIntent, isMealIntentEnabled } from '@/ai/meal-intent'
import { useDailyStore } from '@/stores/daily'
import type { MealGoal, MealIntent } from '@/types/api'

const GOAL_LABELS: Record<MealGoal, string> = {
  balanced: '均衡',
  weight_control: '克制能量',
  high_protein: '高蛋白',
}

const dailyStore = useDailyStore()
const enabled = isMealIntentEnabled()
const text = ref('')
const parsing = ref(false)
const failed = ref(false)
const intent = ref<MealIntent | null>(null)

const canSubmit = computed(() => text.value.trim().length > 0)
const goalLabel = computed(() =>
  intent.value?.goal ? GOAL_LABELS[intent.value.goal] : '',
)

/** 把当前意图写回 store；下一次推荐请求会带上它。 */
function commit(next: MealIntent | null): void {
  intent.value = next
  if (next) {
    dailyStore.setMealIntent(next)
  } else {
    dailyStore.clearMealIntent()
  }
}

async function onParse(): Promise<void> {
  if (parsing.value || !canSubmit.value) return
  parsing.value = true
  failed.value = false
  try {
    const parsed = await extractMealIntent(text.value)
    if (parsed) {
      commit(parsed)
    } else {
      // 静默降级：不提交任何约束，也不打断基础推荐。
      failed.value = true
      commit(null)
    }
  } finally {
    parsing.value = false
  }
}

function removeAvailable(item: string): void {
  if (!intent.value) return
  commit({
    ...intent.value,
    availableIngredients: intent.value.availableIngredients.filter(
      (value) => value !== item,
    ),
  })
}

function removeExcluded(item: string): void {
  if (!intent.value) return
  commit({
    ...intent.value,
    excludedIngredients: intent.value.excludedIngredients.filter(
      (value) => value !== item,
    ),
  })
}

function clearTime(): void {
  if (!intent.value) return
  commit({ ...intent.value, maxTimeMinutes: null })
}

function clearGoal(): void {
  if (!intent.value) return
  commit({ ...intent.value, goal: null })
}

function onClear(): void {
  text.value = ''
  failed.value = false
  commit(null)
}
</script>

<style lang="scss" scoped>
.ai-panel {
  background: $card;
  border-radius: $radius-lg;
  padding: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: $shadow-card;
}

.ai-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.ai-input {
  flex: 1;
  height: 76rpx;
  background: $bg;
  border-radius: 999rpx;
  padding: 0 28rpx;
  font-size: 26rpx;
  color: $ink;
}

.ai-btn {
  background: $grad-brand;
  border-radius: 999rpx;
  padding: 0 32rpx;
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-btn-off {
  opacity: 0.55;
}

.ai-btn-text {
  color: #fff;
  font-size: 26rpx;
  font-weight: 600;
}

.ai-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 20rpx;
}

.ai-tag {
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
}

.ai-tag-has {
  background: $fresh-light;
}

.ai-tag-no {
  background: $warning-light;
}

.ai-tag-time {
  background: $brand-light;
}

.ai-tag-goal {
  background: $brand-light;
}

.ai-tag-clear {
  background: $bg;
}

.ai-tag-text {
  font-size: 22rpx;
  color: $ink-2;
}

.ai-summary {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $ink-3;
  line-height: 1.5;
}

.ai-hint {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  color: $ink-3;
}
</style>
