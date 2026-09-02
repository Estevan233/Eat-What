<template>
  <view class="page">
    <view class="hero">
      <image class="hero-avatar" src="/static/brand-avatar.png" mode="aspectFill" />
      <view class="hero-text">
        <text class="hero-title">{{ APP_NAME }}</text>
        <text class="hero-kicker">{{ HERO_TITLE }}</text>
        <text class="hero-sub">{{ BRAND_SUBTITLE }}</text>
      </view>
    </view>
    <WeatherBadge ref="badgeRef" class="context-badge" />

    <view class="mode-switch" aria-label="用餐方式">
      <view
        class="mode-option"
        :class="{ 'mode-on': dailyStore.diningMode === 'cook' }"
        @click="selectMode('cook')"
      >
        <text class="mode-icon">🍳</text>
        <view class="mode-copy">
          <text class="mode-title">自己做</text>
          <text class="mode-sub">搭配一套家常餐</text>
        </view>
      </view>
      <view
        class="mode-option"
        :class="{ 'mode-on': dailyStore.diningMode === 'eat_out' }"
        @click="selectMode('eat_out')"
      >
        <text class="mode-icon">🥡</text>
        <view class="mode-copy">
          <text class="mode-title">点外卖 / 到店吃</text>
          <text class="mode-sub">先选菜，再搜附近店</text>
        </view>
      </view>
    </view>

    <AiMealIntentInput />

    <view v-if="dailyStore.todayCount > 0" class="chosen-banner" hover-class="chosen-banner-hover" @click="goDiary">
      <text class="chosen-mark">✓</text>
      <view class="chosen-copy">
        <text class="chosen-title">今日已安排 {{ dailyStore.todayCount }}/3 餐</text>
        <text v-if="chosenMealNames" class="chosen-text">{{ chosenMealNames }}</text>
        <text v-else class="chosen-text">去餐食日记看看今天吃了什么吧</text>
      </view>
      <text class="history-link">日记 ›</text>
    </view>

    <!-- 选择器 summary（收起态） -->
    <view v-if="!selectorsExpanded" class="panel-summary" @click="toggleSelectors">
      <text class="panel-summary-text">用餐设置：{{ selectorSummary }}</text>
      <text class="panel-summary-edit">✎</text>
    </view>

    <!-- 选择器面板（展开态） -->
    <view v-show="selectorsExpanded" class="panel">
      <view class="panel-header">
        <text class="panel-header-label">用餐设置</text>
        <text class="panel-header-toggle" @click="toggleSelectors">收起</text>
      </view>
      <view class="panel-row">
        <text class="panel-label">哪一餐</text>
        <view class="chip-row">
          <text
            v-for="option in MEAL_SLOT_OPTIONS"
            :key="option.value"
            class="chip meal-chip"
            :class="{ 'chip-on': dailyStore.mealSlot === option.value }"
            @click="selectMealSlot(option.value)"
          >{{ option.emoji }} {{ option.label }}<text v-if="recordedSlots.has(option.value)" class="slot-done"> ✓</text></text>
        </view>
      </view>
      <view class="panel-row">
        <text class="panel-label">为谁吃</text>
        <view class="chip-row">
          <text
            class="chip"
            :class="{ 'chip-on': dailyStore.audience === 'personal' }"
            @click="selectAudience('personal')"
          >👤 个人</text>
          <text
            class="chip"
            :class="{ 'chip-on': dailyStore.audience === 'family' }"
            @click="selectAudience('family')"
          >👨‍👩‍👧 家庭</text>
        </view>
      </view>
      <view v-if="dailyStore.audience === 'family'" class="panel-row">
        <text class="panel-label">几个人</text>
        <view class="chip-row">
          <text
            v-for="size in PARTY_SIZES"
            :key="size"
            class="chip party-chip"
            :class="{ 'chip-on': dailyStore.partySize === size }"
            @click="selectPartySize(size)"
          >{{ size }} 人</text>
        </view>
      </view>
      <view v-if="dailyStore.diningMode === 'eat_out'" class="city-field">
        <view class="city-head">
          <text class="panel-label">所在城市</text>
          <text class="city-note">不授权定位也能用</text>
        </view>
        <input
          class="city-input"
          :value="dailyStore.city"
          maxlength="64"
          placeholder="例如：杭州（可不填）"
          confirm-type="done"
          @blur="onCityInput"
          @confirm="onCityInput"
        />
      </view>
      <view class="panel-row">
        <text class="panel-label">心情</text>
        <view class="chip-row">
          <text
            v-for="m in MOOD_LIST"
            :key="m"
            class="chip"
            :class="{ 'chip-on': dailyStore.mood === m }"
            @click="dailyStore.setMood(m)"
          >{{ MOOD_EMOJI[m] }} {{ MOOD_LABELS[m] }}</text>
        </view>
      </view>
      <view class="panel-row">
        <text class="panel-label">活动量</text>
        <view class="chip-row">
          <text
            v-for="a in ACTIVITY_LIST"
            :key="a"
            class="chip"
            :class="{ 'chip-on': dailyStore.activityLevel === a }"
            @click="dailyStore.setActivityLevel(a)"
          >{{ ACTIVITY_EMOJI[a] }} {{ ACTIVITY_LABELS[a] }}</text>
        </view>
      </view>
      <text v-if="dailyStore.audience === 'family'" class="family-hint">
        家庭模式优先考虑共享、少折腾；能量仍按每人估算，不拿锅的大小装科学。
      </text>
    </view>

    <button class="cta" :disabled="isLoading" @click="onRecommend">
      {{ ctaText }}
    </button>

    <view v-if="pageError" class="error-banner">
      <text class="error-title">这次没有拿到新推荐</text>
      <text class="error-copy">{{ pageError }}</text>
      <text v-if="requestId" class="request-id">请求编号：{{ requestId }}</text>
    </view>

    <view v-if="isLoading" class="skeleton-card" />

    <template v-else-if="dailyStore.diningMode === 'cook'">
      <view v-if="dailyStore.currentMeal" class="result">
        <view v-if="dailyStore.stale || dailyStore.offline" class="cache-banner">
          <text class="cache-title">{{ dailyStore.offline ? '当前离线 · 展示上次推荐' : '上次推荐' }}</text>
          <text class="cache-copy">可以查看菜谱；刷新成功前不能换菜或确认。</text>
        </view>

        <MealPlateCard
          :meal="dailyStore.currentMeal"
          :party-size="dailyStore.partySize"
          :readonly="dailyStore.stale || dailyStore.offline"
          @open-recipe="openRecipe"
          @choose="chooseCurrentMeal"
        />

        <AiRecommendationExplanation :meal-names="recommendedMealNames" />

        <view v-if="dailyStore.availableSubstitutions.length" class="substitutions">
          <view class="section-head">
            <text class="section-title">想换个口味？</text>
            <text class="section-tip">热量尽量控制在相近范围</text>
          </view>
          <MealSubstitution
            v-for="item in dailyStore.availableSubstitutions"
            :key="`${item.targetRole}-${item.replacement.foodId}`"
            :substitution="item"
            :readonly="dailyStore.stale || dailyStore.offline"
            @apply="dailyStore.applySubstitution(item)"
          />
        </view>
        <text v-else-if="dailyStore.serverRecommendation?.substitutionNotice" class="notice">
          {{ dailyStore.serverRecommendation.substitutionNotice }}
        </text>

        <RecommendationBasis
          v-if="dailyStore.serverRecommendation"
          :profile="dailyStore.serverRecommendation.weightProfile"
          :disclaimer="dailyStore.serverRecommendation.wellnessDisclaimer"
        />
      </view>

      <view v-else class="empty">
        <text class="empty-emoji">🍚</text>
        <text class="empty-title">还没有今天的完整餐</text>
        <text class="empty-text">点击上方按钮，会搭配主菜、蔬菜和主食，并标出每份估算能量。</text>
        <button v-if="pageError" class="empty-retry" @click="onRecommend">重新获取</button>
      </view>
    </template>

    <template v-else>
      <view v-if="diningStore.recommendation" class="external-result">
        <view class="external-head">
          <view>
            <text class="section-title">先选吃什么，再去搜店</text>
            <text class="external-place">{{ diningStore.recommendation.cityLabel }} · {{ dailyStore.partySize }} 人</text>
          </view>
          <navigator class="memory-link" url="/pages/dining-memory/dining-memory">我的记录 ›</navigator>
        </view>
        <ExternalDiningCard
          v-for="suggestion in diningStore.recommendation.suggestions"
          :key="suggestion.key"
          :suggestion="suggestion"
          @remember="openMemory"
        />
        <text class="external-disclaimer">{{ diningStore.recommendation.disclaimer }}</text>

        <view v-if="specialties.length" class="specialty">
          <view class="specialty-head">
            <text class="specialty-title">🍜 {{ dailyStore.city }} 的本地味道</text>
            <text class="specialty-badge">AI 推荐 · 仅供参考</text>
          </view>
          <text class="specialty-sub">到了当地，这些才值得专门去吃</text>
          <view v-for="item in specialties" :key="item.name" class="specialty-item">
            <text class="specialty-name">{{ item.name }}</text>
            <text class="specialty-reason">{{ item.reason }}</text>
          </view>
        </view>
      </view>

      <view v-else class="empty">
        <text class="empty-emoji">🥡</text>
        <text class="empty-title">不想做饭，也不用瞎点</text>
        <text class="empty-text">先给出菜品类型、能量区间和下单提醒；不接商家、不替你下单，也不假装知道实时价格。</text>
        <button v-if="pageError" class="empty-retry" @click="onRecommend">重新获取</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AiMealIntentInput from '@/components/AiMealIntentInput.vue'
import AiRecommendationExplanation from '@/components/AiRecommendationExplanation.vue'
import ExternalDiningCard from '@/components/ExternalDiningCard.vue'
import MealPlateCard from '@/components/MealPlateCard.vue'
import MealSubstitution from '@/components/MealSubstitution.vue'
import RecommendationBasis from '@/components/RecommendationBasis.vue'
import WeatherBadge from '@/components/WeatherBadge.vue'
import { MEAL_SLOT_OPTIONS } from '@/ai/meal-log'
import { getCitySpecialties } from '@/api/dining'
import { useLocation, type Coords } from '@/composables/useLocation'
import { APP_NAME, BRAND_SUBTITLE, HERO_TITLE } from '@/config/brand'
import { ACTIVITY_LABELS, ACTIVITY_LIST, MOOD_LABELS, MOOD_LIST } from '@/constants/daily'
import { useDailyStore } from '@/stores/daily'
import { useDiningStore } from '@/stores/dining'
import { useFavoriteStore } from '@/stores/favorite'
import { useUserStore } from '@/stores/user'
import { ApiError } from '@/types/api'
import type { MealSlot } from '@/types/api'
import type {
  ActivityLevel,
  Audience,
  CitySpecialty,
  DiningMode,
  ExternalDiningSuggestion,
  MealItem,
  Mood,
} from '@/types/api'

const dailyStore = useDailyStore()
const diningStore = useDiningStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()
const { getLocation } = useLocation()
const badgeRef = ref<InstanceType<typeof WeatherBadge> | null>(null)
const pageError = ref('')
const selectorsExpanded = ref(false)
const specialties = ref<CitySpecialty[]>([])
const PARTY_SIZES = [2, 3, 4, 5, 6, 8]

const MOOD_EMOJI: Record<Mood, string> = {
  happy: '😄', neutral: '😌', tired: '😪', stressed: '😣', anxious: '😰',
}
const ACTIVITY_EMOJI: Record<ActivityLevel, string> = {
  light: '🚶', normal: '🚶‍♂️', high: '🏃',
}
const selectorSummary = computed(() => {
  const parts: string[] = []
  parts.push(dailyStore.diningMode === 'eat_out' ? '外卖' : '自己做')
  if (dailyStore.audience === 'family') {
    parts.push(`${dailyStore.partySize}人`)
  } else {
    parts.push('个人')
  }
  parts.push(MOOD_LABELS[dailyStore.mood])
  parts.push(ACTIVITY_LABELS[dailyStore.activityLevel])
  return parts.join(' · ')
})
function toggleSelectors() {
  selectorsExpanded.value = !selectorsExpanded.value
}
const isLoading = computed(() => dailyStore.diningMode === 'cook'
  ? dailyStore.loading
  : diningStore.loading)
const requestId = computed(() => dailyStore.diningMode === 'cook'
  ? dailyStore.lastRequestId
  : diningStore.lastRequestId)
const ctaText = computed(() => {
  if (isLoading.value) return '正在帮你取舍…'
  if (dailyStore.diningMode === 'eat_out') return '🥡 给我 3 个外食方向'
  return dailyStore.audience === 'family'
    ? `🍽 给 ${dailyStore.partySize} 人选一套菜`
    : '🍽 换一套完整餐'
})
const chosenMealNames = computed(() => {
  const chunks: string[] = []
  for (const slot of MEAL_SLOT_OPTIONS) {
    const log = dailyStore.todayLogs.find(
      (entry) => entry.mealSlot === slot.value && entry.chosenMeal?.items?.length,
    )
    if (!log?.chosenMeal?.items?.length) continue
    const names = log.chosenMeal.items.map((item) => item.name).join(' · ')
    chunks.push(`${slot.label}：${names}`)
  }
  return chunks.join('；')
})
/** 今天已有记录的餐次（chips 上的 ✓ 角标数据源）。 */
const recordedSlots = computed(() => new Set(dailyStore.todayLogs.map((log) => log.mealSlot)))
const recommendedMealNames = computed(() => {
  return dailyStore.currentMeal?.items?.map((item) => item.name) || []
})

function selectMode(mode: DiningMode): void {
  dailyStore.setDiningMode(mode)
  if (mode === 'cook') diningStore.clearRecommendation()
  else dailyStore.clearMealRecommendation()
  pageError.value = ''
  if (mode === 'cook') specialties.value = []
}

function selectMealSlot(slot: MealSlot): void {
  dailyStore.setMealSlot(slot)
}

function goDiary(): void {
  // 日记是 tabBar 页面，必须用 switchTab 才能跳转
  uni.switchTab({ url: '/pages/history/history' })
}

/** 从后端拉取当前城市特色菜；AI 不可用时静默为空（区块隐藏）。 */
async function refreshSpecialties(): Promise<void> {
  const city = dailyStore.city.trim()
  if (!city) {
    specialties.value = []
    return
  }
  try {
    const result = await getCitySpecialties(city)
    specialties.value = result.items || []
  } catch {
    specialties.value = []
  }
}

function selectAudience(audience: Audience): void {
  dailyStore.setAudience(audience)
  diningStore.clearRecommendation()
  pageError.value = ''
}

function selectPartySize(size: number): void {
  dailyStore.setPartySize(size)
  diningStore.clearRecommendation()
  pageError.value = ''
}

function onCityInput(event: Event): void {
  const inputEvent = event as unknown as { detail?: { value?: string } }
  dailyStore.setCity(inputEvent.detail?.value || '')
  diningStore.clearRecommendation()
  // 城市变化后旧城市的特色菜不再可信。
  specialties.value = []
}

async function onRecommend(): Promise<void> {
  if (isLoading.value) return
  pageError.value = ''
  if (!userStore.isLoggedIn) {
    uni.navigateTo({ url: '/pages/auth/auth' })
    return
  }
  if (dailyStore.diningMode === 'cook' && !userStore.hasProfile) {
    uni.showToast({ title: '请先填写健康档案', icon: 'none' })
    uni.switchTab({ url: '/pages/profile/profile' })
    return
  }

  let coords: Coords | null = null
  const needsLocation = dailyStore.diningMode === 'eat_out'
    ? !dailyStore.city
    : !dailyStore.hasFreshWeather
  if (needsLocation) {
    try {
      coords = await getLocation()
    } catch {
      // 拒绝定位不会阻断：自己做使用通用上下文，外食可手填城市。
    }
  }

  try {
    if (dailyStore.diningMode === 'eat_out') {
      await diningStore.fetchRecommendation({
        mood: dailyStore.mood,
        activityLevel: dailyStore.activityLevel,
        audience: dailyStore.audience,
        partySize: dailyStore.partySize,
        city: dailyStore.city || undefined,
        lat: coords?.lat,
        lng: coords?.lng,
      })
      uni.showToast({ title: '外食方向已整理', icon: 'none' })
      if (dailyStore.city.trim()) refreshSpecialties()
    } else {
      await dailyStore.fetchRecommend(coords?.lat, coords?.lng)
      uni.showToast({ title: dailyStore.offline ? '已展示上次推荐' : '完整餐已搭配', icon: 'none' })
    }
    if (coords) badgeRef.value?.refreshWeather?.()
  } catch (error) {
    const apiError = error instanceof ApiError ? error : null
    pageError.value = apiError?.code === 'SERVICE_CONFIG_ERROR'
      ? '云托管服务尚未正确配置，请把请求编号发给开发者。'
      : (apiError?.message || '请检查网络后重试。')
  }
}

function openRecipe(item: MealItem): void {
  uni.navigateTo({ url: `/pages/recipe/recipe?foodId=${item.foodId}` })
}

function openMemory(suggestion: ExternalDiningSuggestion): void {
  const params = [
    `dishName=${encodeURIComponent(suggestion.dishName)}`,
    `shopName=${encodeURIComponent(suggestion.shopName || '')}`,
  ].join('&')
  uni.navigateTo({ url: `/pages/dining-memory/dining-memory?${params}` })
}

async function chooseCurrentMeal(): Promise<void> {
  try {
    await dailyStore.chooseCurrentMeal()
    uni.showToast({ title: '今天就吃这套', icon: 'success' })
  } catch {
    // request 层或禁用状态已经给出明确反馈。
  }
}

onShow(() => {
  if (userStore.isLoggedIn) {
    dailyStore.fetchTodayLogs().catch(() => undefined)
    favoriteStore.fetchList().catch(() => undefined)
  }
  setTimeout(() => badgeRef.value?.refreshWeather?.(), 100)
  // 无推荐结果时自动展开选择器，有结果时收起
  selectorsExpanded.value = !dailyStore.currentMeal
})

onShareAppMessage(() => {
  return {
    title: '饭卜卜 · 今天吃啥嘞？',
    path: '/pages/today/today',
  }
})

onShareTimeline(() => {
  return {
    title: '饭卜卜 · 今天吃啥嘞？',
  }
})

</script>

<style lang="scss" scoped>
.page { min-height: 100vh; background: $bg; padding: 22rpx 32rpx 70rpx; box-sizing: border-box; }
.hero { display: flex; align-items: center; gap: 24rpx; padding: 40rpx 6rpx 30rpx; }
.hero-avatar { width: 108rpx; height: 108rpx; flex: 0 0 108rpx; border-radius: 32rpx; box-shadow: $shadow-card; }
.hero-text { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 8rpx; }
.hero-title { color: $ink; font-size: 46rpx; font-weight: 800; letter-spacing: 2rpx; line-height: 1.15; }
.hero-kicker { color: $brand-deep; font-size: 24rpx; font-weight: 750; letter-spacing: 1rpx; }
.hero-sub { color: $ink-2; font-size: 22rpx; line-height: 1.5; }
.context-badge { margin: 0 6rpx 18rpx; max-width: calc(100% - 12rpx); box-sizing: border-box; }
.mode-switch { display: flex; gap: 12rpx; margin-bottom: 20rpx; padding: 10rpx; border: 1rpx solid $line; border-radius: 28rpx; background: rgba(255, 255, 255, .72); }
.mode-option { min-width: 0; flex: 1; display: flex; align-items: center; gap: 12rpx; padding: 19rpx 18rpx; border-radius: 21rpx; color: $ink-2; transition: transform .18s ease, background-color .18s ease; }
.mode-option:active { transform: scale(.98); }
.mode-on { color: $brand-deep; background: $brand-light; box-shadow: inset 0 0 0 1rpx $brand-soft; }
.mode-icon { flex: 0 0 auto; font-size: 32rpx; }
.mode-copy { min-width: 0; display: flex; flex-direction: column; gap: 3rpx; }
.mode-title { font-size: 23rpx; font-weight: 800; }
.mode-sub { font-size: 17rpx; white-space: nowrap; }
.chosen-banner { display: flex; align-items: center; gap: 14rpx; margin-bottom: 20rpx; padding: 20rpx 22rpx; border: 1rpx solid $fresh-light; border-radius: $radius-md; background: $fresh-light; transition: transform .12s ease; }
.chosen-banner-hover { transform: scale(.985); }
.chosen-mark { width: 42rpx; height: 42rpx; flex: 0 0 42rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; background: $fresh; font-size: 23rpx; font-weight: 800; }
.chosen-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 4rpx; }
.chosen-title { color: $fresh-dark; font-size: 24rpx; font-weight: 750; }
.chosen-text { color: $fresh; font-size: 21rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-link { color: $fresh; font-size: 22rpx; }
.meal-chip { padding: 9rpx 20rpx; }
.slot-done { color: $fresh; font-weight: 800; }
.specialty { padding: 26rpx 26rpx 12rpx; border: 1rpx solid $brand-soft; border-radius: $radius-lg; background: $brand-light; }
.specialty-head { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; }
.specialty-title { color: $brand-dark; font-size: 27rpx; font-weight: 800; }
.specialty-badge { flex: 0 0 auto; padding: 5rpx 12rpx; border-radius: 999rpx; color: $brand; background: #fff; border: 1rpx solid $brand-soft; font-size: 17rpx; font-weight: 650; }
.specialty-sub { display: block; margin-top: 6rpx; color: $ink-3; font-size: 19rpx; }
.specialty-item { display: flex; flex-direction: column; gap: 4rpx; margin-top: 18rpx; padding: 16rpx 18rpx; border-radius: 18rpx; background: #fff; }
.specialty-name { color: $ink; font-size: 24rpx; font-weight: 750; }
.specialty-reason { color: $ink-2; font-size: 20rpx; line-height: 1.5; }
.panel { margin-bottom: 26rpx; padding: 28rpx; border-radius: $radius-lg; background: $card; box-shadow: $shadow-card; }
.panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20rpx; }
.panel-header-label { color: $ink; font-size: 28rpx; font-weight: 750; }
.panel-header-toggle { color: $brand; font-size: 24rpx; }
.panel-summary { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16rpx; padding: 20rpx 28rpx; border-radius: $radius-lg; background: $brand-light; border: 1rpx solid $brand-soft; }
.panel-summary-text { color: $brand-dark; font-size: 24rpx; font-weight: 650; }
.panel-summary-edit { color: $brand; font-size: 28rpx; }
.panel-row { display: flex; align-items: flex-start; gap: 14rpx; margin-bottom: 22rpx; }
.panel-label { width: 104rpx; flex: 0 0 104rpx; padding-top: 10rpx; color: $ink-2; font-size: 24rpx; font-weight: 650; }
.chip-row { flex: 1; display: flex; flex-wrap: wrap; gap: 10rpx; }
.chip { padding: 9rpx 18rpx; border: 1rpx solid $line; border-radius: 999rpx; color: $ink-2; background: $bg; font-size: 22rpx; }
.chip-on { color: $brand-dark; border-color: $brand-soft; background: $brand-light; font-weight: 650; }
.party-chip { min-width: 58rpx; text-align: center; }
.city-field { margin-bottom: 22rpx; }
.city-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10rpx; }
.city-head .panel-label { width: auto; flex: initial; padding: 0; }
.city-note { color: $fresh; font-size: 19rpx; }
.city-input { height: 76rpx; padding: 0 22rpx; border: 1rpx solid $line; border-radius: 20rpx; color: $ink; background: $bg; font-size: 23rpx; }
.family-hint { display: block; margin: -2rpx 0 18rpx 118rpx; color: $ink-3; font-size: 18rpx; line-height: 1.5; }
.cta { height: 94rpx; line-height: 94rpx; margin-top: 8rpx; border: none; border-radius: 999rpx; color: #fff; background: $grad-brand; box-shadow: $shadow-cta; font-size: 29rpx; font-weight: 750; }
.cta::after { border: none; }
.cta[disabled] { color: #fff; opacity: .65; }
.error-banner, .cache-banner { display: flex; flex-direction: column; gap: 6rpx; margin-bottom: 20rpx; padding: 20rpx 22rpx; border-radius: 20rpx; }
.cache-banner { flex-direction: row; align-items: center; gap: 10rpx; padding: 12rpx 22rpx; border-radius: 999rpx; margin-bottom: 12rpx; }
.error-banner { color: $danger; background: #fff0eb; border: 1rpx solid #ffd0c2; }
.cache-banner { color: $warning-dark; background: $warning-light; border: 1rpx solid #f1df9e; }
.error-title, .cache-title { font-size: 24rpx; font-weight: 750; }
.error-copy, .cache-copy, .request-id { font-size: 21rpx; line-height: 1.5; }
.request-id { word-break: break-all; opacity: .75; }
.skeleton-card { height: 720rpx; border-radius: 36rpx; background: linear-gradient(100deg, $line 20%, $bg 50%, $line 80%); background-size: 220% 100%; animation: shimmer 1.4s infinite; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.result, .external-result { display: flex; flex-direction: column; gap: 22rpx; }
.external-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 20rpx; padding: 4rpx 4rpx 0; }
.external-head > view { display: flex; flex-direction: column; gap: 5rpx; }
.external-place { color: $ink-3; font-size: 20rpx; }
.memory-link { flex: 0 0 auto; color: $brand; font-size: 21rpx; }
.external-disclaimer { padding: 0 10rpx; color: $ink-3; font-size: 18rpx; line-height: 1.55; text-align: center; }
.substitutions { display: flex; flex-direction: column; gap: 12rpx; padding: 24rpx; border-radius: 28rpx; background: rgba(255, 255, 255, .72); border: 1rpx solid $line; }
.section-head { display: flex; align-items: baseline; justify-content: space-between; gap: 20rpx; padding: 0 4rpx 8rpx; }
.section-title { color: $ink; font-size: 28rpx; font-weight: 750; }
.section-tip { color: $ink-3; font-size: 19rpx; text-align: right; }
.notice { padding: 18rpx 22rpx; border-radius: 20rpx; color: $ink-2; background: #fff; border: 1rpx solid $line; font-size: 22rpx; line-height: 1.55; }
.empty { min-height: 420rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14rpx; padding: 40rpx 24rpx; text-align: center; }
.empty-emoji { font-size: 78rpx; }
.empty-title { color: $ink; font-size: 29rpx; font-weight: 700; }
.empty-text { max-width: 560rpx; color: $ink-3; font-size: 23rpx; line-height: 1.65; }
.empty-retry { min-width: 220rpx; height: 88rpx; line-height: 88rpx; margin-top: 12rpx; border-radius: 999rpx; color: #fff; background: $brand; font-size: 25rpx; }
.empty-retry::after { border: none; }
@media (max-width: 340px) {
  .page { padding-left: 24rpx; padding-right: 24rpx; }
  .hero { gap: 14rpx; }
  .hero-avatar { width: 88rpx; height: 88rpx; flex-basis: 88rpx; }
  .hero-title { font-size: 42rpx; }
  .panel { padding: 24rpx; }
  .mode-option { padding: 16rpx 13rpx; }
  .mode-icon { display: none; }
  .panel-label { width: 92rpx; flex-basis: 92rpx; }
  .family-hint { margin-left: 106rpx; }
}
</style>
