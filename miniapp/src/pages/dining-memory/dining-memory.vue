<template>
  <view class="page">
    <view class="intro">
      <text class="intro-kicker">PRIVATE FOOD NOTES</text>
      <text class="intro-title">记住具体哪家、哪道菜</text>
      <text class="intro-copy">只对“店铺＋菜品”这组组合生效。喜欢会优先想起，避雷会被排除。</text>
    </view>

    <view v-if="dateFilter" class="date-filter">
      <text class="date-filter-text">📅 {{ dateFilter }} 的外食</text>
      <text class="date-filter-clear" @click="clearDateFilter">查看全部 ✕</text>
    </view>

    <view class="form-card">
      <view class="form-header" @click="toggleForm">
        <view class="form-header-left">
          <text class="form-title">{{ formExpanded ? '记一笔' : '记一笔新记录' }}</text>
          <text v-if="!formExpanded && hasDraft" class="form-draft">已填写内容，点击继续</text>
        </view>
        <view class="form-toggle">
          <text class="form-toggle-text">{{ formExpanded ? '收起' : '展开' }}</text>
          <text class="form-toggle-icon" :class="{ 'form-toggle-on': formExpanded }">▾</text>
        </view>
      </view>

      <view v-show="formExpanded" class="form-body">
        <view class="field-row">
          <view class="field field-half">
            <text class="label">店铺名称</text>
            <input
              class="input"
              :value="shopName"
              maxlength="80"
              placeholder="例如：楼下小王食堂"
              @input="onShopInput"
            />
          </view>
          <view class="field field-half">
            <text class="label">菜品名称</text>
            <input
              class="input"
              :value="dishName"
              maxlength="80"
              placeholder="例如：番茄鸡蛋盖饭"
              @input="onDishInput"
            />
          </view>
        </view>
        <view class="field">
          <text class="label">这次印象</text>
          <view class="verdicts">
            <text
              v-for="item in VERDICTS"
              :key="item.value"
              class="verdict"
              :class="[`verdict-${item.value}`, { 'verdict-on': verdict === item.value }]"
              @click="verdict = item.value"
            >{{ item.icon }} {{ item.label }}</text>
          </view>
        </view>
        <view class="field">
          <text class="label">私人备注</text>
          <textarea
            class="textarea"
            :value="note"
            maxlength="500"
            placeholder="例如：少油好吃；午高峰太慢；下次不要辣……"
            @input="onNoteInput"
          />
          <text class="counter">{{ note.length }}/500</text>
        </view>
        <button class="save" :disabled="!canSave || diningStore.saving" @click="saveMemory">
          {{ diningStore.saving ? '正在保存…' : '保存这条记录' }}
        </button>
      </view>
    </view>

    <view class="list-section">
      <view class="list-head">
        <view>
          <text class="list-title">我的外食记录</text>
          <text class="list-count">{{ searchQuery ? `找到 ${diningStore.memories.length} 条` : `${diningStore.memories.length} 条` }}</text>
        </view>
        <text class="privacy">🔒 仅当前账号可见</text>
      </view>

      <view class="search-box">
        <text class="search-icon">🔍</text>
        <input
          class="search-input"
          :value="searchQuery"
          maxlength="64"
          placeholder="搜店名、菜名或备注"
          confirm-type="search"
          @input="onSearchQueryInput"
          @confirm="loadMemories"
        />
        <text v-if="searchQuery" class="search-clear" @click="clearSearchQuery">✕</text>
      </view>

      <view v-if="loading" class="loading">正在翻你的美食小账本…</view>
      <view v-else-if="diningStore.memories.length" class="memory-list">
        <view v-for="item in diningStore.memories" :key="item.id" class="memory-card">
          <view class="memory-main" @click="editMemory(item)">
            <view class="memory-title-row">
              <text class="memory-dish">{{ item.dishName }}</text>
              <text class="memory-verdict" :class="`memory-${item.verdict}`">{{ verdictText(item.verdict) }}</text>
            </view>
            <text class="memory-shop">{{ item.shopName }}</text>
            <text v-if="item.note" class="memory-note">“{{ item.note }}”</text>
            <text v-else class="memory-note memory-empty-note">没有备注，点击可补充</text>
          </view>
          <text class="delete" @click="confirmDelete(item.id)">删除</text>
        </view>
      </view>
      <view v-else class="empty">
        <text class="empty-icon">{{ searchQuery ? '🔍' : '🧾' }}</text>
        <text class="empty-title">{{ searchQuery ? `没有找到「${searchQuery}」的记录` : '还没有记录' }}</text>
        <text class="empty-copy">
          {{ searchQuery ? '换个关键词试试，或在上面直接记一条新的。' : '下次吃到惊喜或踩雷，别只在脑子里骂两句。' }}
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useDiningStore } from '@/stores/dining'
import { useUserStore } from '@/stores/user'
import { ApiError } from '@/types/api'
import type { DiningMemoryRead, DiningVerdict } from '@/types/api'

const diningStore = useDiningStore()
const userStore = useUserStore()
const shopName = ref('')
const dishName = ref('')
const note = ref('')
const verdict = ref<DiningVerdict>('neutral')
const loading = ref(false)
const searchQuery = ref('')
const formExpanded = ref(true)
const dateFilter = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined

const VERDICTS: Array<{ value: DiningVerdict; label: string; icon: string }> = [
  { value: 'liked', label: '喜欢', icon: '👍' },
  { value: 'neutral', label: '一般', icon: '😐' },
  { value: 'avoided', label: '避雷', icon: '⚠️' },
]

const canSave = computed(() => shopName.value.trim().length > 0 && dishName.value.trim().length > 0)
const hasDraft = computed(() => shopName.value.trim().length > 0 || dishName.value.trim().length > 0 || note.value.trim().length > 0)

function inputValue(event: Event): string {
  const inputEvent = event as unknown as { detail?: { value?: string } }
  return inputEvent.detail?.value || ''
}

function onShopInput(event: Event): void {
  shopName.value = inputValue(event)
}

function onDishInput(event: Event): void {
  dishName.value = inputValue(event)
}

function onNoteInput(event: Event): void {
  note.value = inputValue(event)
}

function verdictText(value: DiningVerdict): string {
  return VERDICTS.find((item) => item.value === value)?.label || '一般'
}

function clearForm(): void {
  shopName.value = ''
  dishName.value = ''
  note.value = ''
  verdict.value = 'neutral'
}

function toggleForm(): void {
  formExpanded.value = !formExpanded.value
}

function queryValue(value: unknown): string {
  const raw = value ? String(value) : ''
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}

function editMemory(item: DiningMemoryRead): void {
  shopName.value = item.shopName
  dishName.value = item.dishName
  note.value = item.note || ''
  verdict.value = item.verdict
  formExpanded.value = true
  uni.pageScrollTo({ scrollTop: 0, duration: 240 })
}

async function saveMemory(): Promise<void> {
  if (!canSave.value || diningStore.saving) return
  try {
    await diningStore.saveMemory({
      shopName: shopName.value,
      dishName: dishName.value,
      verdict: verdict.value,
      note: note.value || null,
    })
    clearForm()
    formExpanded.value = diningStore.memories.length === 0
    uni.showToast({ title: '已记下', icon: 'success' })
  } catch (error) {
    const message = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
    uni.showToast({ title: message, icon: 'none' })
  }
}

function confirmDelete(memoryId: number): void {
  uni.showModal({
    title: '删除这条记录？',
    content: '删除后不再用于优先推荐或避雷。',
    success: (result) => {
      if (!result.confirm) return
      diningStore.removeMemory(memoryId)
        .then(() => uni.showToast({ title: '已删除', icon: 'none' }))
        .catch(() => uni.showToast({ title: '删除失败', icon: 'none' }))
    },
  })
}

onLoad((query) => {
  shopName.value = queryValue(query?.shopName)
  dishName.value = queryValue(query?.dishName)
  dateFilter.value = queryValue(query?.date)
})

async function loadMemories(): Promise<void> {
  loading.value = true
  try {
    await diningStore.fetchMemories(
      undefined,
      searchQuery.value.trim(),
      dateFilter.value || undefined,
    )
  } catch {
    uni.showToast({ title: '外食记录加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function clearDateFilter(): void {
  dateFilter.value = ''
  loadMemories()
}

function onSearchQueryInput(event: Event): void {
  searchQuery.value = inputValue(event)
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadMemories()
  }, 300)
}

function clearSearchQuery(): void {
  searchQuery.value = ''
  loadMemories()
}

onShow(async () => {
  if (!userStore.isLoggedIn) {
    uni.navigateTo({ url: '/pages/auth/auth' })
    return
  }
  await loadMemories()
  formExpanded.value = diningStore.memories.length === 0
})

onShareAppMessage(() => {
  return {
    title: '饭卜卜 · 外食记录',
    path: '/pages/dining-memory/dining-memory',
  }
})

onShareTimeline(() => {
  return {
    title: '饭卜卜 · 外食记录',
  }
})

</script>

<style lang="scss" scoped>
.page { display: flex; flex-direction: column; min-height: 100vh; padding: 32rpx 32rpx 80rpx; box-sizing: border-box; background: $bg; }
.intro { display: flex; flex-direction: column; gap: 8rpx; padding: 20rpx 8rpx 24rpx; }
.intro-kicker { color: $brand; font-size: 18rpx; font-weight: 800; letter-spacing: 3rpx; }
.intro-title { color: $ink; font-size: 36rpx; font-weight: 850; }
.intro-copy { color: $ink-2; font-size: 22rpx; line-height: 1.55; }

.form-card { padding: 24rpx 24rpx 28rpx; border-radius: $radius-lg; background: $card; box-shadow: $shadow-card; }
.form-header { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; }
.form-header-left { display: flex; align-items: center; gap: 16rpx; min-width: 0; }
.form-title { color: $ink; font-size: 29rpx; font-weight: 800; }
.form-draft { color: $brand; font-size: 21rpx; font-weight: 600; }
.form-toggle { display: flex; align-items: center; gap: 8rpx; padding: 8rpx 16rpx; border-radius: 999rpx; background: $bg; }
.form-toggle-text { color: $ink-2; font-size: 21rpx; }
.form-toggle-icon { color: $ink-2; font-size: 21rpx; transition: transform .2s ease; }
.form-toggle-on { transform: rotate(180deg); }

.form-body { margin-top: 24rpx; }
.field-row { display: flex; gap: 16rpx; }
.field { position: relative; display: flex; flex-direction: column; gap: 10rpx; margin-bottom: 20rpx; }
.field-half { flex: 1; min-width: 0; }
.label { color: $ink; font-size: 22rpx; font-weight: 700; }
.input, .textarea { padding: 0 20rpx; border: 1rpx solid $line; border-radius: 18rpx; color: $ink; background: $bg; font-size: 23rpx; box-sizing: border-box; }
.input { height: 76rpx; }
.textarea { width: 100%; height: 140rpx; padding-top: 18rpx; padding-bottom: 36rpx; line-height: 1.5; }
.counter { position: absolute; right: 16rpx; bottom: 12rpx; color: $ink-3; font-size: 17rpx; }
.verdicts { display: flex; gap: 12rpx; }
.verdict { flex: 1; padding: 14rpx 10rpx; border: 1rpx solid $line; border-radius: 18rpx; color: $ink-2; background: $bg; font-size: 21rpx; text-align: center; }
.verdict-on { color: $ink; border-color: $brand-soft; background: $brand-light; font-weight: 750; }
.verdict-avoided.verdict-on { color: #9b2c1f; border-color: #ffc9bd; background: #fff0ec; }
.verdict-liked.verdict-on { color: #237438; border-color: #bfe8c8; background: $fresh-light; }
.save { height: 86rpx; line-height: 86rpx; margin: 4rpx 0 0; border-radius: 999rpx; color: #fff; background: $grad-brand; box-shadow: $shadow-cta; font-size: 27rpx; font-weight: 750; }
.save::after { border: none; }
.save[disabled] { color: #fff; opacity: .48; }

.list-section { flex: 1; display: flex; flex-direction: column; min-height: 0; margin-top: 28rpx; }
.list-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 20rpx; margin: 0 6rpx 18rpx; }
.list-head > view { display: flex; align-items: baseline; gap: 12rpx; }
.list-title { color: $ink; font-size: 29rpx; font-weight: 800; }
.list-count, .privacy { color: $ink-3; font-size: 19rpx; }
.memory-list { display: flex; flex-direction: column; gap: 14rpx; }
.memory-card { display: flex; align-items: center; gap: 16rpx; padding: 24rpx; border: 1rpx solid $line; border-radius: 26rpx; background: $card; }
.memory-main { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 7rpx; }
.memory-title-row { display: flex; align-items: center; gap: 12rpx; }
.memory-dish { min-width: 0; color: $ink; font-size: 27rpx; font-weight: 750; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.memory-verdict { flex: 0 0 auto; padding: 4rpx 11rpx; border-radius: 999rpx; color: $ink-2; background: $bg; font-size: 17rpx; }
.memory-liked { color: #237438; background: $fresh-light; }
.memory-avoided { color: #9b2c1f; background: #fff0ec; }
.memory-shop { color: $brand; font-size: 20rpx; font-weight: 650; }
.memory-note { color: $ink-2; font-size: 20rpx; line-height: 1.45; }
.memory-empty-note { color: $ink-3; }
.delete { flex: 0 0 auto; padding: 16rpx 4rpx 16rpx 16rpx; color: #c34c36; font-size: 20rpx; }
.loading, .empty { min-height: 260rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; color: $ink-3; font-size: 22rpx; text-align: center; }
.empty { gap: 10rpx; }
.empty-icon { font-size: 58rpx; }
.empty-title { color: $ink; font-size: 26rpx; font-weight: 700; }
.empty-copy { max-width: 480rpx; line-height: 1.55; }
.search-box {
  display: flex;
  align-items: center;
  gap: 10rpx;
  height: 84rpx;
  margin-bottom: 20rpx;
  padding: 0 24rpx;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  background: $card;
  box-shadow: $shadow-card;
  box-sizing: border-box;
}
.search-icon { font-size: 26rpx; }
.search-input { flex: 1; min-width: 0; color: $ink; font-size: 25rpx; }
.search-clear {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  color: $ink-3;
  background: $bg;
  font-size: 22rpx;
}
.date-filter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  margin: 4rpx 6rpx 18rpx;
  padding: 14rpx 20rpx;
  border-radius: 18rpx;
  background: $brand-light;
  border: 1rpx solid $brand-soft;
}
.date-filter-text {
  color: $brand-dark;
  font-size: 24rpx;
  font-weight: 700;
}
.date-filter-clear {
  color: $ink-2;
  font-size: 22rpx;
}
</style>
