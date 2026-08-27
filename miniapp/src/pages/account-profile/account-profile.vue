<template>
  <view class="page">
    <view class="intro">
      <text class="eyebrow">公开资料</text>
      <text class="title">让饭卜卜认识你</text>
      <text class="subtitle">身份认证已经完成。头像昵称由你主动选择，也可以稍后再填。</text>
    </view>

    <view class="profile-card">
      <button
        class="avatar-button"
        open-type="chooseAvatar"
        :disabled="saving"
        @chooseavatar="onChooseAvatar"
      >
        <image v-if="avatarPreview" class="avatar-image" :src="avatarPreview" mode="aspectFill" />
        <view v-else class="avatar-placeholder">
          <uni-icons type="camera" size="30" color="#e8590c" />
          <text class="avatar-hint">选择头像</text>
        </view>
      </button>

      <view class="field">
        <text class="field-label">怎么称呼你</text>
        <input
          v-model="nickname"
          class="nickname-input"
          type="nickname"
          maxlength="64"
          placeholder="输入昵称"
          :disabled="saving"
        />
      </view>

      <view class="privacy-note">
        <uni-icons type="locked" size="16" color="#8f847d" />
        <text>仅用于饭卜卜内展示，不会公开你的 openid</text>
      </view>

      <view class="save-button" :class="{ disabled: saving }" @click="saveAndContinue">
        <text>{{ saving ? '保存中…' : '保存并继续' }}</text>
      </view>
      <view class="skip-button" :class="{ disabled: saving }" @click="skip">
        <text>先跳过</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { dismissProfileOnboarding } from '@/auth/profile-onboarding'
import { resolvePostLoginNavigation } from '@/auth/navigation'
import { uploadProfileAvatar } from '@/profile/avatar-upload'
import { useUserStore } from '@/stores/user'

type ChooseAvatarEvent = {
  detail: { avatarUrl?: string }
}

const userStore = useUserStore()
const nickname = ref('')
const avatarPreview = ref('')
const redirect = ref<string | undefined>()
const saving = ref(false)

onLoad((query) => {
  redirect.value = typeof query?.redirect === 'string' ? query.redirect : undefined
  const user = userStore.profile
  if (!user) {
    uni.redirectTo({ url: '/pages/auth/auth' })
    return
  }
  nickname.value = ['微信用户', '用户'].includes(user.nickname) ? '' : user.nickname
  avatarPreview.value = user.avatarUrl || ''
})

function onChooseAvatar(event: ChooseAvatarEvent) {
  if (event.detail.avatarUrl) avatarPreview.value = event.detail.avatarUrl
}

function continueToDestination() {
  const navigation = resolvePostLoginNavigation(redirect.value)
  if (navigation.method === 'switchTab') uni.switchTab({ url: navigation.url })
  else uni.redirectTo({ url: navigation.url })
}

async function saveAndContinue() {
  const user = userStore.profile
  if (!user || saving.value) return
  const cleanNickname = nickname.value.trim()
  if (!cleanNickname || !avatarPreview.value) {
    uni.showToast({ title: '请选择头像并填写昵称', icon: 'none' })
    return
  }

  saving.value = true
  try {
    const avatarUrl = avatarPreview.value.startsWith('cloud://')
      || avatarPreview.value.startsWith('https://')
      ? avatarPreview.value
      : await uploadProfileAvatar(user.id, avatarPreview.value)
    await userStore.saveAccountProfile({ nickname: cleanNickname, avatarUrl })
    uni.showToast({ title: '资料已保存', icon: 'success' })
    continueToDestination()
  } catch (error) {
    console.error('[profile] save account profile failed', error)
    uni.showToast({
      title: error instanceof Error ? error.message : '保存失败，请稍后重试',
      icon: 'none',
    })
  } finally {
    saving.value = false
  }
}

function skip() {
  const user = userStore.profile
  if (!user || saving.value) return
  dismissProfileOnboarding(user.id)
  continueToDestination()
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 96rpx 36rpx 48rpx;
  background: $bg;
}

.intro {
  padding: 0 24rpx 80rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.eyebrow {
  color: $brand;
  font-size: 24rpx;
  font-weight: 700;
  letter-spacing: 4rpx;
  margin-bottom: 18rpx;
}

.title {
  color: $ink;
  font-size: 52rpx;
  line-height: 1.2;
  font-weight: 800;
  margin-bottom: 20rpx;
}

.subtitle {
  max-width: 560rpx;
  color: $ink-2;
  font-size: 26rpx;
  line-height: 1.7;
}

.profile-card {
  position: relative;
  padding: 108rpx 36rpx 28rpx;
  border-radius: 40rpx;
  background: $card;
  box-shadow: $shadow-card;
}

.avatar-button {
  position: absolute;
  top: -58rpx;
  right: 46rpx;
  width: 148rpx;
  height: 148rpx;
  padding: 0;
  border: 8rpx solid $bg;
  border-radius: 48rpx;
  overflow: hidden;
  background: $brand-light;
  box-shadow: $shadow-cta;
  line-height: normal;

  &::after { border: 0; }
}

.avatar-image,
.avatar-placeholder {
  width: 100%;
  height: 100%;
}

.avatar-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
}

.avatar-hint {
  color: $brand;
  font-size: 20rpx;
  font-weight: 600;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.field-label {
  color: $ink;
  font-size: 28rpx;
  font-weight: 700;
}

.nickname-input {
  height: 92rpx;
  box-sizing: border-box;
  padding: 0 28rpx;
  border: 2rpx solid $line;
  border-radius: 24rpx;
  background: $bg;
  color: $ink;
  font-size: 30rpx;
}

.privacy-note {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin: 22rpx 4rpx 42rpx;
  color: $ink-3;
  font-size: 22rpx;
}

.save-button {
  height: 92rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $grad-brand;
  box-shadow: $shadow-cta;
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
}

.skip-button {
  height: 80rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $ink-2;
  font-size: 26rpx;
}

.disabled { opacity: 0.6; }
</style>
