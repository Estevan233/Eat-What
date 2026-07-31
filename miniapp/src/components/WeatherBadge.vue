<template>
  <view class="badge">
    <text v-if="loading" class="text-muted">加载中…</text>
    <!-- 未登录：只显示节气/星座（公开 API） -->
    <view v-else-if="!userStore.isLoggedIn" class="ctx-row">
      <text v-if="dailyStore.todayContext" class="chip">
        {{ zodiacLabel }} · {{ ctxAnimal }} · {{ solarTermText }}
      </text>
      <text v-else class="text-muted">历法信息暂不可用</text>
    </view>
    <!-- 已登录：节气 + 天气（含位置授权引导） -->
    <view v-else class="ctx-row">
      <text v-if="dailyStore.todayContext" class="chip">
        {{ zodiacLabel }}
      </text>
      <text v-if="dailyStore.todayContext" class="sep">·</text>
      <text v-if="dailyStore.todayContext" class="chip chip-term">
        {{ solarTermText }}
      </text>
      <template v-if="weatherChipText">
        <text class="sep">·</text>
        <text class="chip chip-weather" :style="{ color: weatherColor }">
          {{ weatherChipText }}
        </text>
      </template>
      <template v-else-if="permissionDenied">
        <text class="sep">·</text>
        <text
          class="chip chip-grant"
          @click="onGrantLocation"
        >
          点击授权位置
        </text>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDailyStore } from '@/stores/daily'
import { useUserStore } from '@/stores/user'
import { ZODIAC_NAMES_ZH, daysUntilSolarTerm } from '@/constants/zodiac'
import { WEATHER_TAG_COLOR, WEATHER_TAG_LABEL } from '@/constants/weather'
import { useLocation, type Coords } from '@/composables/useLocation'
import type { TodayContext } from '@/types/api'

const userStore = useUserStore()
const dailyStore = useDailyStore()
const loading = ref(true)
const { permissionDenied, getLocation, requestPermission } = useLocation()

const ctx = computed<TodayContext | null>(() => dailyStore.todayContext)

const zodiacLabel = computed(() =>
  ctx.value ? ZODIAC_NAMES_ZH[ctx.value.zodiacSign] : '',
)
const ctxAnimal = computed(() => ctx.value?.animal || '')
const solarTermText = computed(() => {
  if (!ctx.value) return ''
  const c = ctx.value.solarTermCurrent
  if (c) return c
  const days = daysUntilSolarTerm(ctx.value.solarTermNextDate)
  return days > 0
    ? `距${ctx.value.solarTermNextName}还有 ${days} 天`
    : ctx.value.solarTermNextName
})

const weather = computed(() => dailyStore.weather)
const weatherChipText = computed(() => {
  if (!weather.value) return ''
  const temp = Math.round(weather.value.tempC)
  return `${temp}° ${weather.value.text} · ${WEATHER_TAG_LABEL[weather.value.weatherTag]}`
})
const weatherColor = computed(() => {
  if (!weather.value) return '#2563eb'
  return WEATHER_TAG_COLOR[weather.value.weatherTag]
})

onMounted(async () => {
  try {
    // 拉节气（公开 API，不需登录）
    await dailyStore.fetchTodayContext()
  } catch {
    // 拉节气失败不影响天气
  }
  loading.value = false
})

/** 拉天气前需登录 + 位置授权；由外部按钮/today.vue onShow 触发。 */
async function refreshWeather(): Promise<void> {
  if (!userStore.isLoggedIn) return
  if (dailyStore.weather && isFresh(dailyStore.weather.fetchedAt)) return
  try {
    const coords: Coords = await getLocation()
    await dailyStore.fetchWeather(coords.lat, coords.lng)
  } catch {
    // 已 toast 由 request 层处理；permissionDenied 状态会更新
  }
}

/** 是否在 1 小时内（缓存有效）。 */
function isFresh(fetchedAtIso: string): boolean {
  const ts = new Date(fetchedAtIso).getTime()
  return Date.now() - ts < 3600_000
}

/** 用户点击「点击授权位置」。 */
async function onGrantLocation(): Promise<void> {
  const granted = await requestPermission()
  if (granted) {
    await refreshWeather()
  }
}

// 暴露给 today 页 onShow 调用
defineExpose({ refreshWeather })
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
  flex-wrap: wrap;
}

.chip {
  font-size: 24rpx;
  color: #2563eb;
}

.chip-term {
  color: #047857;
}

.chip-weather {
  font-weight: 600;
}

.chip-grant {
  color: #d97706;
  text-decoration: underline;
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