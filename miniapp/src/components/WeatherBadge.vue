<template>
  <view class="badge">
    <text v-if="loading" class="text-muted">加载中…</text>
    <view v-else-if="!ctx" class="text-muted">历法信息暂不可用</view>
    <view v-else class="ctx-row">
      <text class="chip chip-zodiac">{{ zodiacLabel }}</text>
      <text class="sep">·</text>
      <text class="chip chip-animal">{{ ctx.animal }}</text>
      <text class="sep">·</text>
      <text class="chip chip-term">{{ solarTermText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getToday } from '@/api/context'
import { ZODIAC_NAMES_ZH, daysUntilSolarTerm } from '@/constants/zodiac'
import type { TodayContext } from '@/types/api'

const ctx = ref<TodayContext | null>(null)
const loading = ref(true)

const zodiacLabel = computed(() =>
  ctx.value ? ZODIAC_NAMES_ZH[ctx.value.zodiacSign] : '',
)

const solarTermText = computed(() => {
  if (!ctx.value) return ''
  const c = ctx.value.solarTermCurrent
  if (c) return c // 节气当天
  const next = ctx.value.solarTermNextName
  const days = daysUntilSolarTerm(ctx.value.solarTermNextDate)
  // 路径与 PRD 一致：「距<next>还有 X 天」
  return days > 0 ? `距${next}还有 ${days} 天` : next
})

onMounted(async () => {
  try {
    ctx.value = await getToday()
  } catch {
    ctx.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style lang="scss" scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 12rpx 24rpx;
  background: #f4f7ff;
  border-radius: 32rpx;
  border: 1rpx solid #dbe4ff;
}

.ctx-row {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
}

.chip {
  font-size: 24rpx;
  color: #2563eb;
}

.chip-zodiac {
  font-weight: 600;
}

.chip-animal {
  color: #b45309;
}

.chip-term {
  color: #047857;
}

.sep {
  font-size: 22rpx;
  color: #c4d3f0;
}

.text-muted {
  font-size: 24rpx;
  color: #94a3b8;
}
</style>