<template>
  <view v-if="enabled && explanation" class="ai-explanation">
    <text class="ai-explanation-icon">✨</text>
    <text class="ai-explanation-text">{{ explanation }}</text>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { isAiEnabled } from '@/ai/cloud-model'
import { generateRecommendationExplanation } from '@/ai/recommendation-explanation'
import { useDailyStore } from '@/stores/daily'

const props = defineProps<{
  mealNames: string[]
}>()

const enabled = isAiEnabled()
const explanation = ref('')
const dailyStore = useDailyStore()

watch(
  () => props.mealNames,
  async (names) => {
    if (!enabled || names.length === 0) {
      explanation.value = ''
      return
    }
    const intentSummary = dailyStore.mealIntent?.summary || null
    const result = await generateRecommendationExplanation(
      intentSummary,
      names,
      dailyStore.diningMode,
    )
    explanation.value = result || ''
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.ai-explanation {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  background: linear-gradient(135deg, rgba(232, 89, 12, 0.06), rgba(232, 89, 12, 0.02));
  border: 1rpx solid rgba(232, 89, 12, 0.15);
  border-radius: $radius-lg;
  padding: 20rpx 24rpx;
  margin-bottom: 20rpx;
}

.ai-explanation-icon {
  font-size: 28rpx;
  flex-shrink: 0;
}

.ai-explanation-text {
  flex: 1;
  font-size: 25rpx;
  line-height: 1.6;
  color: $ink-2;
}
</style>
