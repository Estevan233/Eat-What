<template>
  <view class="page">
    <!-- 品牌区 -->
    <view class="brand">
      <image class="logo" src="/static/brand-avatar.png" mode="aspectFill" />
      <text class="title">今天吃啥</text>
      <text class="subtitle">每天 3 道菜，结合天气 · 节气 · 心情 · 体质</text>
    </view>

    <!-- 按钮区 -->
    <view class="actions">
      <view class="btn-primary" :class="{ 'btn-disabled': loading }" @click="onLogin">
        <text class="btn-text">{{ loading ? '登录中…' : '微信一键登录' }}</text>
      </view>

      <view class="divider">
        <view class="divider-line" />
        <text class="divider-text">或</text>
        <view class="divider-line" />
      </view>

      <view class="btn-guest" :class="{ 'btn-disabled': loading }" @click="onGuestLogin">
        <text class="btn-guest-text">游客登录，先体验一下</text>
      </view>
    </view>

    <text class="footnote">游客模式无需微信授权，体验完整功能</text>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { shouldShowAuthErrorToast, toAuthErrorMessage } from '@/auth/error'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)

function goNext() {
  const pages = getCurrentPages()
  const last = pages[pages.length - 1]
  const redirect = (last as unknown as { options?: { redirect?: string } }).options?.redirect
  if (redirect) {
    uni.redirectTo({ url: decodeURIComponent(redirect) })
  } else {
    uni.switchTab({ url: '/pages/today/today' })
  }
}

function handleLoginError(action: string, error: unknown) {
  console.error(`[auth] ${action} failed`, error)
  if (shouldShowAuthErrorToast(error)) {
    uni.showToast({ title: toAuthErrorMessage(error), icon: 'none' })
  }
}

async function onLogin() {
  if (loading.value) return
  loading.value = true
  try {
    await userStore.login()
    uni.showToast({ title: '登录成功', icon: 'success' })
    goNext()
  } catch (error) {
    handleLoginError('wx-login', error)
  } finally {
    loading.value = false
  }
}

async function onGuestLogin() {
  if (loading.value) return
  loading.value = true
  try {
    await userStore.loginAsGuest()
    uni.showToast({ title: '已进入游客模式', icon: 'none' })
    goNext()
  } catch (error) {
    handleLoginError('guest-login', error)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: $bg;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 64rpx;
  box-sizing: border-box;
}

/* 品牌区 */
.brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  padding-top: 120rpx;
}

.logo {
  width: 168rpx;
  height: 168rpx;
  border-radius: 48rpx;
  box-shadow: $shadow-cta;
}

.title {
  font-size: 56rpx;
  font-weight: 800;
  color: $ink;
  letter-spacing: 4rpx;
}

.subtitle {
  font-size: 26rpx;
  color: $ink-2;
  text-align: center;
  line-height: 1.6;
}

/* 按钮区 */
.actions {
  width: 100%;
  padding-bottom: 80rpx;
}

.btn-primary {
  background: $grad-brand;
  border-radius: 999rpx;
  padding: 30rpx 0;
  text-align: center;
  box-shadow: $shadow-cta;
}

.btn-disabled {
  opacity: 0.7;
}

.btn-text {
  color: #fff;
  font-size: 32rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.divider {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin: 40rpx 0;
}

.divider-line {
  flex: 1;
  height: 1rpx;
  background: $line;
}

.divider-text {
  font-size: 24rpx;
  color: $ink-3;
}

.btn-guest {
  border: 2rpx solid $brand-soft;
  border-radius: 999rpx;
  padding: 28rpx 0;
  text-align: center;
  background: $card;
}

.btn-guest-text {
  color: $brand;
  font-size: 30rpx;
  font-weight: 600;
}

.footnote {
  font-size: 22rpx;
  color: $ink-3;
  padding-bottom: 40rpx;
}
</style>
