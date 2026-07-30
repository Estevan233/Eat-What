<template>
  <view class="page">
    <!-- 未登录引导 -->
    <view v-if="!userStore.isLoggedIn" class="state-prompt">
      <text class="state-title">登录后可测体质</text>
      <text class="state-hint">体质结果会用于个性化推荐</text>
      <button class="btn-primary" @click="goLogin">去登录</button>
    </view>

    <!-- 无档案引导：体质判定需要先建档案 -->
    <view v-else-if="!hasProfileChecked && profileMissing" class="state-prompt">
      <text class="state-title">先填健康档案再测体质</text>
      <text class="state-hint">体质判定需要存到你的档案</text>
      <button class="btn-primary" @click="goProfile">去填档案</button>
    </view>

    <!-- 加载中 -->
    <view v-else-if="loadingQuestions" class="state-prompt">
      <text class="state-hint">加载题目…</text>
    </view>

    <!-- 结果视图 -->
    <view v-else-if="view === 'result'" class="result-view">
      <view class="result-header">
        <text class="result-label">您的主体质</text>
        <text class="result-primary">{{ primaryLabel }}</text>
        <view v-if="secondaryLabels.length" class="secondary-row">
          <text class="secondary-label">兼夹：</text>
          <view v-for="s in secondaryLabels" :key="s" class="chip">{{ s }}</view>
        </view>
      </view>

      <view class="chart">
        <text class="chart-title">九种体质转化分</text>
        <view v-for="t in CONSTITUTION_TYPES" :key="t" class="bar-row">
          <text class="bar-name">{{ CONSTITUTION_NAMES[t] }}</text>
          <view class="bar-track">
            <view
              class="bar-fill"
              :class="{ 'bar-fill-on': isOn(t) }"
              :style="{ width: barWidth(t) }"
            ></view>
          </view>
          <text class="bar-score" :class="{ 'bar-score-on': isOn(t) }">
            {{ scoreOf(t) }}
          </text>
        </view>
      </view>

      <button class="btn-primary retake-btn" :disabled="submitting" @click="onRetake">
        重新测试
      </button>
    </view>

    <!-- 问卷视图 -->
    <view v-else class="form-view">
      <view class="progress-row">
        <view class="progress-track">
          <view class="progress-fill" :style="{ width: `${(answeredCount / 9) * 100}%` }"></view>
        </view>
        <text class="progress-text">{{ answeredCount }} / 9</text>
      </view>

      <view v-for="(q, idx) in questions" :key="q.id" class="question">
        <view class="q-head">
          <text class="q-no">{{ idx + 1 }}</text>
          <text class="q-text">{{ q.text }}</text>
        </view>
        <radio-group class="q-options" @change="(e: any) => onPick(q.id, e)">
          <label
            v-for="opt in optionList"
            :key="opt.value"
            class="q-opt"
            :class="{ 'q-opt-on': answers[q.id] === opt.value }"
          >
            <radio :value="opt.value" :checked="answers[q.id] === opt.value" />
            <text class="q-opt-label">{{ opt.label }}</text>
          </label>
        </radio-group>
      </view>

      <button
        class="btn-primary submit-btn"
        :disabled="!canSubmit || submitting"
        @click="onSubmit"
      >
        {{ submitting ? '提交中…' : '提交问卷' }}
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { getQuestions } from '@/api/constitution'
import { requireLogin } from '@/utils/auth-guard'
import {
  CONSTITUTION_NAMES,
  CONSTITUTION_OPTIONS,
  CONSTITUTION_TYPES,
} from '@/constants/constitution'
import type {
  ConstitutionOption,
  ConstitutionQuestion,
  ConstitutionType,
} from '@/types/api'

type View = 'form' | 'result'

const userStore = useUserStore()

const view = ref<View>('form')
const loadingQuestions = ref(false)
const submitting = ref(false)
const profileMissing = ref(false)
const hasProfileChecked = ref(false)

const questions = ref<ConstitutionQuestion[]>([])
const optionList = ref<ConstitutionOption[]>([])
// answers: { questionId: value }
const answers = reactive<Record<number, number>>({})

const answeredCount = computed(
  () => Object.keys(answers).filter((k) => answers[Number(k)] !== undefined).length,
)
const canSubmit = computed(() => answeredCount.value === 9)

const result = computed(() => userStore.constitution)
const primaryLabel = computed(() =>
  result.value ? CONSTITUTION_NAMES[result.value.primary] : '',
)
const secondaryLabels = computed(() =>
  result.value ? result.value.secondary.map((s) => CONSTITUTION_NAMES[s]) : [],
)

function scoreOf(t: ConstitutionType): number {
  return result.value?.scoresNormalized?.[t] ?? 0
}

function isOn(t: ConstitutionType): boolean {
  const score = scoreOf(t)
  return score >= 60
}

function barWidth(t: ConstitutionType): string {
  return `${Math.min(100, Math.max(0, scoreOf(t)))}%`
}

function onPick(qid: number, e: { detail: { value: string } }) {
  answers[qid] = Number(e.detail.value)
}

async function loadQuestions() {
  loadingQuestions.value = true
  try {
    const data = await getQuestions()
    questions.value = data.questions
    optionList.value = data.options
  } catch (e) {
    // request 层已 toast；本地兜底用常量避免空白
    questions.value = []
    optionList.value = CONSTITUTION_OPTIONS as unknown as ConstitutionOption[]
  } finally {
    loadingQuestions.value = false
  }
}

async function ensureProfile() {
  // 没拉过档案就拉一次；profile=null 即视为没建档
  if (!userStore.userProfile) {
    try {
      await userStore.fetchUserProfile()
    } catch {
      // 拉失败视为没档案
    }
  }
  hasProfileChecked.value = true
  profileMissing.value = userStore.userProfile === null
}

async function ensureConstitution() {
  try {
    await userStore.fetchConstitution()
    view.value = 'result'
  } catch {
    // 404 = 还没测过，留在问卷视图；其它错误 request 层已 toast
    view.value = 'form'
  }
}

onMounted(async () => {
  if (!userStore.isLoggedIn) return // onLoad 已守卫，但再次保险
  await ensureProfile()
  if (profileMissing.value) return
  await loadQuestions()
  await ensureConstitution()
})

async function onSubmit() {
  if (submitting.value || !canSubmit.value) return
  submitting.value = true
  try {
    await userStore.saveConstitution({ ...answers })
    uni.showToast({ title: '判定完成', icon: 'success' })
    view.value = 'result'
  } catch (e) {
    const msg = e instanceof Error ? e.message : '提交失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function onRetake() {
  for (const k of Object.keys(answers)) {
    delete answers[Number(k)]
  }
  view.value = 'form'
}

function goLogin() {
  requireLogin('/pages/constitution/constitution')
}

function goProfile() {
  uni.navigateTo({ url: '/pages/profile/profile' })
}
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx 30rpx;
  min-height: 100vh;
  background: #f8f8f8;
}

.state-prompt {
  margin-top: 200rpx;
  text-align: center;
}

.state-title {
  display: block;
  font-size: 40rpx;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 16rpx;
}

.state-hint {
  display: block;
  font-size: 26rpx;
  color: #888;
  margin-bottom: 40rpx;
}

/* ---- 问卷视图 ---- */

.progress-row {
  display: flex;
  align-items: center;
  margin-bottom: 30rpx;
}

.progress-track {
  flex: 1;
  height: 12rpx;
  background: #e5e7eb;
  border-radius: 6rpx;
  overflow: hidden;
  margin-right: 20rpx;
}

.progress-fill {
  height: 100%;
  background: #2563eb;
  transition: width 0.2s ease;
}

.progress-text {
  font-size: 24rpx;
  color: #888;
  min-width: 80rpx;
  text-align: right;
}

.question {
  background: #fff;
  border-radius: 16rpx;
  padding: 30rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.q-head {
  display: flex;
  align-items: flex-start;
  margin-bottom: 20rpx;
}

.q-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40rpx;
  height: 40rpx;
  border-radius: 20rpx;
  background: #2563eb;
  color: #fff;
  font-size: 24rpx;
  font-weight: 600;
  margin-right: 16rpx;
  flex-shrink: 0;
  margin-top: 4rpx;
}

.q-text {
  flex: 1;
  font-size: 30rpx;
  color: #1f2937;
  line-height: 1.5;
}

.q-options {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx 24rpx;
}

.q-opt {
  display: inline-flex;
  align-items: center;
  padding: 8rpx 16rpx;
  border-radius: 8rpx;
  border: 1rpx solid transparent;
}

.q-opt-on {
  background: #eff6ff;
  border-color: #2563eb;
}

.q-opt-label {
  margin-left: 8rpx;
  font-size: 28rpx;
  color: #333;
}

.submit-btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background: #2563eb;
  color: #fff;
  font-size: 32rpx;
  border-radius: 44rpx;
  border: none;
  margin-top: 30rpx;
}

.submit-btn[disabled] {
  background: #93b7f3;
}

.btn-primary {
  display: inline-block;
  margin-top: 30rpx;
  padding: 16rpx 40rpx;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 28rpx;
}

/* ---- 结果视图 ---- */

.result-view {
  padding-top: 20rpx;
}

.result-header {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx 24rpx;
  text-align: center;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.result-label {
  display: block;
  font-size: 24rpx;
  color: #888;
  margin-bottom: 12rpx;
}

.result-primary {
  display: block;
  font-size: 56rpx;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 16rpx;
}

.secondary-row {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12rpx;
}

.secondary-label {
  font-size: 26rpx;
  color: #555;
}

.chip {
  padding: 8rpx 20rpx;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 32rpx;
  font-size: 26rpx;
}

.chart {
  background: #fff;
  border-radius: 16rpx;
  padding: 30rpx 24rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.chart-title {
  display: block;
  font-size: 28rpx;
  color: #1f2937;
  font-weight: 600;
  margin-bottom: 24rpx;
}

.bar-row {
  display: flex;
  align-items: center;
  margin-bottom: 16rpx;
}

.bar-name {
  width: 130rpx;
  font-size: 24rpx;
  color: #555;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 24rpx;
  background: #f0f0f0;
  border-radius: 12rpx;
  overflow: hidden;
  margin: 0 16rpx;
}

.bar-fill {
  height: 100%;
  background: #c4d3f0;
  transition: width 0.3s ease;
}

.bar-fill-on {
  background: #2563eb;
}

.bar-score {
  width: 60rpx;
  font-size: 24rpx;
  color: #888;
  text-align: right;
  flex-shrink: 0;
}

.bar-score-on {
  color: #2563eb;
  font-weight: 600;
}

.retake-btn {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  background: #fff;
  color: #2563eb;
  border: 1rpx solid #2563eb;
  border-radius: 40rpx;
  font-size: 28rpx;
}

.retake-btn[disabled] {
  color: #93b7f3;
  border-color: #93b7f3;
}
</style>
