<template>
  <view class="page">
    <view class="header">
      <text class="title">健康档案</text>
      <text class="hint">用来给你定个性化的吃啥建议</text>
    </view>

    <view v-if="!userStore.isLoggedIn" class="login-prompt">
      <text>登录后才能编辑档案</text>
      <button class="btn-primary" @click="goLogin">去登录</button>
    </view>

    <view v-else class="form">
      <!-- 生日 -->
      <view class="field">
        <text class="label">生日</text>
        <picker mode="date" :value="form.birthday" :end="todayStr" @change="onBirthdayChange">
          <view class="picker-value">{{ form.birthday || '请选择日期' }}</view>
        </picker>
      </view>

      <!-- 性别 -->
      <view class="field">
        <text class="label">性别</text>
        <radio-group @change="onGenderChange">
          <label v-for="g in genderOptions" :key="g.value" class="radio-item">
            <radio :value="g.value" :checked="form.gender === g.value" />
            <text class="radio-label">{{ g.label }}</text>
          </label>
        </radio-group>
      </view>

      <!-- 身高 -->
      <view class="field">
        <text class="label">身高 (cm)</text>
        <input
          v-model="heightCmInput"
          class="input"
          type="number"
          placeholder="80-250"
          maxlength="3"
        />
      </view>

      <!-- 体重 -->
      <view class="field">
        <text class="label">体重 (kg)</text>
        <input
          v-model="weightKgInput"
          class="input"
          type="digit"
          placeholder="30-300"
          maxlength="6"
        />
      </view>

      <!-- 忌口标签 -->
      <view class="field">
        <text class="label">忌口标签（多选）</text>
        <view class="chip-row">
          <view
            v-for="tag in FORBIDDEN_TAGS"
            :key="tag"
            class="chip"
            :class="{ 'chip-on': form.forbiddenTags.includes(tag) }"
            @click="toggleTag(tag)"
          >
            <text>{{ FORBIDDEN_TAGS_LABEL[tag] }}</text>
          </view>
        </view>
      </view>

      <button class="btn-primary submit-btn" :disabled="submitting" @click="onSubmit">
        {{ submitting ? '保存中…' : '保存档案' }}
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { requireLogin } from '@/utils/auth-guard'
import { FORBIDDEN_TAGS, FORBIDDEN_TAGS_LABEL, type ForbiddenTag } from '@/constants/forbidden-tags'
import type { Gender, ProfileUpsert } from '@/types/api'

const userStore = useUserStore()
const submitting = ref(false)

const genderOptions: ReadonlyArray<{ value: Gender; label: string }> = [
  { value: 'male', label: '男' },
  { value: 'female', label: '女' },
  { value: 'other', label: '其他' },
]

// 表单初值
const form = reactive<ProfileUpsert>({
  birthday: '',
  gender: 'male',
  heightCm: undefined,
  weightKg: undefined,
  forbiddenTags: [],
})

// input 绑定用 string，提交时再转 number；用 ref 而不是 form 上的字段，
// 因为 uni-app input v-model 永远是 string，类型上不匹配 number。
const heightCmInput = ref('')
const weightKgInput = ref('')

// 今日字符串，picker 的 end 上限
const todayStr = new Date().toISOString().slice(0, 10)

function goLogin() {
  requireLogin('/pages/profile/profile')
}

function onBirthdayChange(e: { detail: { value: string } }) {
  form.birthday = e.detail.value
}

function onGenderChange(e: { detail: { value: Gender } }) {
  form.gender = e.detail.value
}

function toggleTag(tag: ForbiddenTag) {
  const idx = form.forbiddenTags.indexOf(tag)
  if (idx >= 0) {
    form.forbiddenTags.splice(idx, 1)
  } else {
    form.forbiddenTags.push(tag)
  }
}

function prefillForm() {
  const p = userStore.userProfile
  if (!p) return
  form.birthday = p.birthday
  form.gender = p.gender
  heightCmInput.value = p.heightCm !== undefined ? String(p.heightCm) : ''
  weightKgInput.value = p.weightKg !== undefined ? String(p.weightKg) : ''
  form.forbiddenTags = [...p.forbiddenTags]
}

onMounted(async () => {
  if (!userStore.isLoggedIn) return // onLoad 已守卫，但再次保险
  // 有缓存的档案就直接预填，没有就拉一次
  if (!userStore.userProfile) {
    try {
      await userStore.fetchUserProfile()
    } catch {
      // 拉失败也无所谓，用户可以填新档案
    }
  }
  prefillForm()
})

async function onSubmit() {
  if (submitting.value) return

  // 前端基础校验
  if (!form.birthday) {
    uni.showToast({ title: '请选生日', icon: 'none' })
    return
  }
  if (!form.gender) {
    uni.showToast({ title: '请选性别', icon: 'none' })
    return
  }
  let heightCm: number | undefined
  let weightKg: number | undefined
  if (heightCmInput.value !== '') {
    const h = Number(heightCmInput.value)
    if (!Number.isFinite(h) || h < 80 || h > 250) {
      uni.showToast({ title: '身高需在 80-250', icon: 'none' })
      return
    }
    heightCm = h
  }
  if (weightKgInput.value !== '') {
    const w = Number(weightKgInput.value)
    if (!Number.isFinite(w) || w < 30 || w > 300) {
      uni.showToast({ title: '体重需在 30-300', icon: 'none' })
      return
    }
    weightKg = w
  }

  submitting.value = true
  try {
    const payload: ProfileUpsert = {
      birthday: form.birthday,
      gender: form.gender,
      heightCm,
      weightKg,
      forbiddenTags: [...form.forbiddenTags],
    }
    await userStore.saveUserProfile(payload)
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/today/today' })
    }, 600)
  } catch (e) {
    const msg = e instanceof Error ? e.message : '保存失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.page {
  padding: 40rpx;
  min-height: 100vh;
  background: #f8f8f8;
}

.header {
  margin-bottom: 60rpx;
  text-align: center;
}

.title {
  display: block;
  font-size: 48rpx;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 12rpx;
}

.hint {
  display: block;
  font-size: 24rpx;
  color: #888;
}

.login-prompt {
  margin-top: 100rpx;
  text-align: center;
  color: #888;
}

.form {
  background: #fff;
  border-radius: 16rpx;
  padding: 30rpx 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
}

.field {
  padding: 24rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.field:last-of-type {
  border-bottom: none;
}

.label {
  display: block;
  font-size: 26rpx;
  color: #555;
  margin-bottom: 16rpx;
}

.picker-value {
  font-size: 30rpx;
  color: #1f2937;
  padding: 8rpx 0;
}

.radio-item {
  display: inline-flex;
  align-items: center;
  margin-right: 30rpx;
}

.radio-label {
  margin-left: 8rpx;
  font-size: 28rpx;
  color: #1f2937;
}

.input {
  font-size: 30rpx;
  border: 1rpx solid #e5e7eb;
  border-radius: 8rpx;
  padding: 16rpx 20rpx;
  width: 100%;
  box-sizing: border-box;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.chip {
  padding: 12rpx 24rpx;
  border: 1rpx solid #e5e7eb;
  border-radius: 32rpx;
  font-size: 26rpx;
  color: #555;
  background: #fff;
}

.chip-on {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.submit-btn {
  width: 100%;
  margin-top: 40rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: #2563eb;
  color: #fff;
  font-size: 32rpx;
  border-radius: 44rpx;
  border: none;
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
</style>
