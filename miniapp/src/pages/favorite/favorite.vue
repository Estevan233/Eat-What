<template>
  <view class="page">
    <!-- 头部 -->
    <view class="heading">
      <view class="title-row">
        <text class="page-title">我的收藏</text>
        <text class="add-chip" @click="openAddCustom">＋ 自定义收藏</text>
      </view>
      <text class="page-sub">搜菜名、翻备注；吃到没进菜谱的好东西，也可以手动记一笔。</text>
    </view>

    <!-- 搜索 -->
    <view class="search-box">
      <text class="search-icon">🔍</text>
      <input
        class="search-input"
        :value="query"
        maxlength="64"
        placeholder="搜菜名、分类或备注"
        confirm-type="search"
        @input="onQueryInput"
        @confirm="refresh(true)"
      />
      <text v-if="query" class="search-clear" @click="clearQuery">✕</text>
    </view>

    <!-- 列表 -->
    <view v-if="loading && items.length === 0" class="hint">正在整理你的收藏…</view>
    <view v-else-if="items.length === 0" class="empty">
      <text class="empty-emoji">{{ query ? '🔍' : '♡' }}</text>
      <text class="empty-title">{{ query ? `没有找到「${query}」的收藏` : '还没有收藏' }}</text>
      <text class="empty-text">
        {{ query ? '换个关键词试试，或把这道记住的自定义收藏起来' : '吃过的喜欢的菜，收藏起来下次接着吃' }}
      </text>
      <button v-if="query" class="empty-cta" @click="openCustom(query)">✍️ 记为自定义收藏</button>
    </view>
    <view v-else class="list">
      <text class="result-hint">共 {{ totalText }} 项收藏</text>
      <view
        v-for="item in items"
        :key="item.favoriteId"
        class="fav-card"
        :class="{ tappable: isNormal(item) }"
      >
        <view class="fav-main" @click="onTapCard(item)">
          <view class="visual">{{ visualOf(item) }}</view>
          <view class="fav-info">
            <text class="fav-name">{{ nameOf(item) }}</text>
            <text class="fav-meta">{{ metaOf(item) }}</text>
            <text v-if="kcalLine(item)" class="fav-cal">{{ kcalLine(item) }}</text>
            <text
              v-if="item.note"
              class="fav-note"
              :class="{ 'fav-note-expanded': expandedId === item.favoriteId }"
            >“{{ item.note }}”</text>
            <text
              v-if="isCustom(item) && expandedId !== item.favoriteId"
              class="fav-note fav-note-placeholder"
            >点击展开备注</text>
          </view>
        </view>
        <view class="fav-actions">
          <text class="action-btn" @click="openNoteEditor(item)">✎ 备注</text>
          <text class="action-btn danger" @click="confirmDelete(item)">删除</text>
        </view>
      </view>
    </view>

    <!-- 自定义收藏表单弹层 -->
    <view v-if="customOpen" class="overlay" @touchmove.stop.prevent="noop" @click="customOpen = false">
      <view class="sheet" @click.stop>
        <view class="sheet-handle" />
        <view class="sheet-head">
          <text class="sheet-title">自定义收藏</text>
          <text class="sheet-close" @click="customOpen = false">✕</text>
        </view>
        <view class="sheet-body">
          <text class="sheet-tip">菜谱库里没有的、外卖单上喜欢的，都能记在这里。</text>
          <view class="field">
            <text class="field-label">名称</text>
            <input
              class="text-input"
              :value="customName"
              maxlength="80"
              placeholder="例如：王阿姨家的糖醋排骨"
              @input="onCustomNameInput"
            />
          </view>
          <view class="field">
            <text class="field-label">备注（可选）</text>
            <textarea
              class="area-input"
              :value="customNote"
              maxlength="500"
              placeholder="为什么喜欢它、一般点什么、怎么点更好吃……"
              @input="onCustomNoteInput"
            />
          </view>
          <button class="primary-btn" :disabled="!customName.trim() || customSaving" @click="saveCustom">
            {{ customSaving ? '正在保存…' : '保存收藏' }}
          </button>
        </view>
      </view>
    </view>

    <!-- 备注编辑弹层 -->
    <view v-if="noteEditor && noteEditor.id !== null" class="overlay" @touchmove.stop.prevent="noop" @click="closeNoteEditor">
      <view class="sheet" @click.stop>
        <view class="sheet-handle" />
        <view class="sheet-head">
          <text class="sheet-title">编辑备注</text>
          <text class="sheet-close" @click="closeNoteEditor">✕</text>
        </view>
        <view class="sheet-body">
          <view class="field">
            <text class="field-label">对「{{ noteEditor.name }}」说点什么</text>
            <textarea
              class="area-input"
              :value="noteEditor.note"
              maxlength="500"
              placeholder="留个印象，例如：这道菜是这家店的招牌……"
              @input="onEditorNoteInput"
            />
          </view>
          <button class="primary-btn" :disabled="noteSaving" @click="saveNoteEditor">
            {{ noteSaving ? '正在保存…' : '保存备注' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShareAppMessage, onShareTimeline, onShow } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'

import { getRecipe } from '@/api/recipe'
import {
  addCustomFavorite,
  deleteFavorite,
  updateFavoriteNote,
  type FavoriteItem,
} from '@/api/favorite'
import { useFavoriteStore } from '@/stores/favorite'
import type { MealRole } from '@/types/api'

const favoriteStore = useFavoriteStore()
const items = computed(() => favoriteStore.items)
const loading = computed(() => favoriteStore.loading)
const totalText = computed(() => (query.value.trim() ? `找到 ${items.value.length}` : items.value.length))

const query = ref('')
const recipeEnergy = ref<Record<number, number>>({})
const expandedId = ref<number | null>(null)
let searchTimer: ReturnType<typeof setTimeout> | undefined

const icons: Record<MealRole, string> = { main: '🥘', vegetable: '🥬', staple: '🍚' }

function isNormal(item: FavoriteItem): boolean {
  return item.foodId != null
}

function isCustom(item: FavoriteItem): boolean {
  return item.foodId == null
}

function nameOf(item: FavoriteItem): string {
  return item.customName ?? item.food?.name ?? ''
}

function visualOf(item: FavoriteItem): string {
  if (isCustom(item)) return '📌'
  return roleIcon(item.food?.mealRole)
}

function roleIcon(role?: MealRole | null): string {
  return role ? icons[role] : '🍽'
}

function metaOf(item: FavoriteItem): string {
  const food = item.food
  if (isCustom(item)) return '自定义收藏 · 手动记录'
  return food ? `${food.category} · ${food.cookingMethod}` : ''
}

function kcalLine(item: FavoriteItem): string {
  if (isCustom(item)) return ''
  const food = item.food
  if (!food) return ''
  const energy = recipeEnergy.value[food.id]
  if (energy) return `约 ${energy} kcal / 份`
  if (food.recipeReady) return '已收录结构化菜谱，点开查看'
  if (food.caloriesKcalPer100g) {
    return `${Math.round(food.caloriesKcalPer100g)} kcal / 100g（原料参考）`
  }
  return ''
}

function inputValue(event: Event): string {
  const inputEvent = event as unknown as { detail?: { value?: string } }
  return inputEvent.detail?.value || ''
}

function onQueryInput(event: Event): void {
  query.value = inputValue(event)
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    refresh(true)
  }, 300)
}

function clearQuery(): void {
  query.value = ''
  refresh(true)
}

async function refresh(force = false): Promise<void> {
  try {
    await favoriteStore.fetchList(force, query.value)
  } catch {
    // request 层错误提示兜底。
  }
}

async function loadRecipeEnergies(list: FavoriteItem[]): Promise<void> {
  await Promise.all(
    list
      .filter((item) => item.foodId != null && item.food?.recipeReady)
      .map(async (item) => {
        const food = item.food
        if (!food) return
        try {
          const recipe = await getRecipe(food.id)
          recipeEnergy.value[food.id] = Math.round(recipe.nutritionPerServing.energyKcal)
        } catch {
          // 单道菜谱加载失败仍保留卡片与 100g 参考值。
        }
      }),
  )
}

onShow(async () => {
  try {
    const list = await favoriteStore.fetchList(true, query.value)
    await loadRecipeEnergies(list)
  } catch {
    // request 层错误提示兜底。
  }
})

function onTapCard(item: FavoriteItem): void {
  if (isCustom(item)) {
    expandedId.value = expandedId.value === item.favoriteId ? null : item.favoriteId
    return
  }
  const food = item.food
  if (!food) return
  if (!food.recipeReady) {
    uni.showToast({ title: '这道菜的结构化菜谱还在整理', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/recipe/recipe?foodId=${food.id}` })
}

// ---------- 自定义收藏 ----------

const customOpen = ref(false)
const customName = ref('')
const customNote = ref('')
const customSaving = ref(false)

function openAddCustom(): void {
  openCustom('')
}

function openCustom(prefillName = ''): void {
  customName.value = prefillName || ''
  customNote.value = ''
  customOpen.value = true
  customSaving.value = false
}

function onCustomNameInput(event: Event): void {
  customName.value = inputValue(event)
}

function onCustomNoteInput(event: Event): void {
  customNote.value = inputValue(event)
}

async function saveCustom(): Promise<void> {
  const name = customName.value.trim()
  if (!name || customSaving.value) return
  customSaving.value = true
  try {
    await addCustomFavorite({
      customName: name,
      note: customNote.value.trim() || null,
    })
    customOpen.value = false
    uni.showToast({ title: '已收藏', icon: 'success' })
    await refresh(true)
  } catch (error) {
    uni.showToast({ title: errorMessage(error), icon: 'none' })
  } finally {
    customSaving.value = false
  }
}

// ---------- 备注编辑 ----------

interface NoteEditorState {
  id: number | null
  name: string
  note: string
}

const noteEditor = ref<NoteEditorState>({ id: null, name: '', note: '' })
const noteSaving = ref(false)

function openNoteEditor(item: FavoriteItem): void {
  noteEditor.value = {
    id: item.favoriteId,
    name: nameOf(item),
    note: item.note ?? '',
  }
}

function closeNoteEditor(): void {
  noteEditor.value.id = null
}

function onEditorNoteInput(event: Event): void {
  noteEditor.value = { ...noteEditor.value, note: inputValue(event) }
}

async function saveNoteEditor(): Promise<void> {
  const id = noteEditor.value.id
  if (id === null || noteSaving.value) return
  noteSaving.value = true
  try {
    await updateFavoriteNote(id, noteEditor.value.note.trim() || null)
    closeNoteEditor()
    uni.showToast({ title: '备注已保存', icon: 'success' })
    await refresh(true)
  } catch (error) {
    uni.showToast({ title: errorMessage(error), icon: 'none' })
  } finally {
    noteSaving.value = false
  }
}

// ---------- 删除 ----------

function confirmDelete(item: FavoriteItem): void {
  uni.showModal({
    title: '取消收藏？',
    content: `「${nameOf(item)}」将从收藏里移除。`,
    confirmText: '删除',
    confirmColor: '#c34c36',
    success: async (result) => {
      if (!result.confirm) return
      try {
        await deleteFavorite(item.favoriteId)
        favoriteStore.removeLocal(item.foodId)
        if (expandedId.value === item.favoriteId) expandedId.value = null
        uni.showToast({ title: '已取消收藏', icon: 'none' })
        await refresh(true)
      } catch (error) {
        uni.showToast({ title: errorMessage(error), icon: 'none' })
      }
    },
  })
}

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (message) return message.length > 60 ? `${message.slice(0, 60)}…` : message
  return '操作失败，请稍后重试'
}

function noop(): void {
  // 拦截弹层滚动冒泡。
}

onShareAppMessage(() => {
  return {
    title: '饭卜卜 · 我的收藏',
    path: '/pages/favorite/favorite',
  }
})

onShareTimeline(() => {
  return {
    title: '饭卜卜 · 我的收藏',
  }
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 32rpx 32rpx 90rpx;
  box-sizing: border-box;
  background: $bg;
}
.heading {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-bottom: 22rpx;
}
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}
.page-title {
  color: $ink;
  font-size: 42rpx;
  font-weight: 800;
}
.add-chip {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  color: $brand-dark;
  background: $brand-light;
  font-size: 21rpx;
  font-weight: 700;
  box-shadow: 0 4rpx 12rpx rgba(232, 89, 12, 0.12);
}
.page-sub {
  color: $ink-3;
  font-size: 21rpx;
  line-height: 1.55;
}

/* 搜索 */
.search-box {
  display: flex;
  align-items: center;
  gap: 10rpx;
  height: 84rpx;
  margin-bottom: 26rpx;
  padding: 0 24rpx;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  background: $card;
  box-shadow: $shadow-card;
  box-sizing: border-box;
}
.search-icon { font-size: 26rpx; }
.search-input {
  flex: 1;
  min-width: 0;
  color: $ink;
  font-size: 25rpx;
}
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

.hint {
  min-height: 54vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14rpx;
  color: $ink-3;
  font-size: 26rpx;
}
.empty {
  min-height: 48vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14rpx;
  padding: 0 40rpx;
  text-align: center;
}
.empty-emoji { font-size: 78rpx; line-height: 1; }
.empty-title { color: $ink; font-size: 28rpx; font-weight: 750; }
.empty-text { color: $ink-3; font-size: 21rpx; line-height: 1.6; }
.empty-cta {
  height: 84rpx;
  line-height: 84rpx;
  margin-top: 14rpx;
  padding: 0 40rpx;
  border-radius: 999rpx;
  color: #fff;
  background: $grad-brand;
  box-shadow: $shadow-cta;
  font-size: 25rpx;
  font-weight: 700;
}
.empty-cta::after { border: none; }

.list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.result-hint {
  color: $ink-3;
  font-size: 20rpx;
  text-align: center;
}
.fav-card {
  display: flex;
  flex-direction: column;
  padding: 22rpx 22rpx 10rpx;
  border: 1rpx solid $line;
  border-radius: 28rpx;
  background: $card;
  box-shadow: $shadow-card;
}
.tappable .fav-main:active { background: #fffaf6; }
.fav-main {
  display: flex;
  align-items: center;
  gap: 20rpx;
  border-radius: 22rpx;
}
.visual {
  width: 92rpx;
  height: 92rpx;
  flex: 0 0 92rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 26rpx;
  background: $brand-light;
  font-size: 44rpx;
}
.fav-info {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.fav-name { color: $ink; font-size: 29rpx; font-weight: 750; word-break: break-all; }
.fav-meta, .fav-cal { color: $ink-2; font-size: 20rpx; }
.fav-note {
  color: $ink-2;
  font-size: 20rpx;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}
.fav-note-expanded {
  -webkit-line-clamp: unset;
  word-break: break-all;
}
.fav-note-placeholder {
  color: $ink-3;
}
.fav-actions {
  display: flex;
  justify-content: flex-end;
  gap: 28rpx;
  padding-top: 14rpx;
  margin-top: 12rpx;
  border-top: 1rpx dashed $line;
}
.action-btn { color: $brand; font-size: 21rpx; font-weight: 650; padding: 6rpx 4rpx; }
.action-btn.danger { color: #c34c36; }

/* 弹层 */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: flex-end;
  background: rgba(43, 35, 32, 0.45);
  animation: fade-in 0.2s ease;
}
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.sheet {
  width: 100%;
  border-radius: 36rpx 36rpx 0 0;
  background: $card;
  box-shadow: 0 -10rpx 40rpx rgba(43, 35, 32, 0.16);
  animation: slide-up 0.26s ease;
}
@keyframes slide-up {
  from { transform: translateY(60rpx); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.sheet-handle {
  width: 72rpx;
  height: 8rpx;
  margin: 16rpx auto 6rpx;
  border-radius: 999rpx;
  background: $line;
}
.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 32rpx 8rpx;
}
.sheet-title { color: $ink; font-size: 32rpx; font-weight: 800; }
.sheet-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  color: $ink-2;
  background: $bg;
  font-size: 24rpx;
}
.sheet-body {
  max-height: 72vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 10rpx 32rpx calc(env(safe-area-inset-bottom) + 40rpx);
}
.sheet-tip { display: block; color: $ink-3; font-size: 21rpx; line-height: 1.6; margin-bottom: 22rpx; }
.field { display: flex; flex-direction: column; gap: 12rpx; margin-bottom: 24rpx; }
.field-label { color: $ink; font-size: 23rpx; font-weight: 700; }
.text-input {
  width: 100%;
  height: 84rpx;
  padding: 0 22rpx;
  border: 1rpx solid $line;
  border-radius: 18rpx;
  color: $ink;
  background: $bg;
  font-size: 24rpx;
  box-sizing: border-box;
}
.area-input {
  width: 100%;
  height: 190rpx;
  padding: 20rpx 22rpx;
  border: 1rpx solid $line;
  border-radius: 18rpx;
  color: $ink;
  background: $bg;
  font-size: 24rpx;
  line-height: 1.55;
  box-sizing: border-box;
}
.primary-btn {
  height: 90rpx;
  line-height: 90rpx;
  margin-top: 6rpx;
  border-radius: 999rpx;
  color: #fff;
  background: $grad-brand;
  box-shadow: $shadow-cta;
  font-size: 27rpx;
  font-weight: 750;
}
.primary-btn::after { border: none; }
.primary-btn[disabled] { color: #fff; opacity: 0.5; box-shadow: none; }
</style>
