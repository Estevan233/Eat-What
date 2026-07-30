<template>
  <view class="page">
    <view class="hero">
      <text class="title">今天吃啥</text>
      <text class="subtitle">用星座、节气、天气、心情、体质告诉你今天该吃啥</text>
    </view>

    <button class="login-btn" :disabled="loading" @click="onLogin">
      {{ loading ? '登录中…' : '微信一键登录' }}
    </button>

    <view class="divider">
      <view class="line"></view>
      <text class="or">或</text>
      <view class="line"></view>
    </view>

    <button class="guest-btn" :disabled="loading" @click="onGuestLogin">
      游客登录，先体验一下
    </button>

    <text class="hint">登录后才能记录心情、收藏菜品、查看历史</text>
    <text class="hint-guest">游客数据也保存在云端，可随时升级为正式账号</text>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)

async function onLogin() {
  if (loading.value) return
  loading.value = true
  try {
    await userStore.login()
    uni.showToast({ title: '登录成功', icon: 'success' })
    goNext()
  } catch (e) {
    const msg = e instanceof Error ? e.message : '登录失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function onGuestLogin() {
  if (loading.value) return
  loading.value = true
  try {
    await userStore.loginAsGuest()
    uni.showToast({ title: '已进入游客模式', icon: 'success' })
    goNext()
  } catch (e) {
    const msg = e instanceof Error ? e.message : '游客登录失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    loading.value = false
  }
}

/** 根据 query 的 redirect 跳转，没有就回 today tab。 */
function goNext() {
  const pages = getCurrentPages()
  const current = pages[pages.length - 1] as { options?: { redirect?: string } }
  const redirect = current?.options?.redirect

  if (redirect) {
    uni.redirectTo({ url: decodeURIComponent(redirect) })
  } else {
    uni.switchTab({ url: '/pages/today/today' })
  }
}
</script>

<style lang="scss" scoped>
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 60rpx;
}

.hero {
  text-align: center;
  margin-bottom: 80rpx;
}

.title {
  display: block;
  font-size: 72rpx;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 20rpx;
}

.subtitle {
  display: block;
  font-size: 26rpx;
  color: #888;
  line-height: 1.5;
}

.login-btn {
  width: 80%;
  height: 88rpx;
  line-height: 88rpx;
  background: #2563eb;
  color: #fff;
  font-size: 32rpx;
  border-radius: 44rpx;
  border: none;
  margin-bottom: 30rpx;
}

.login-btn[disabled] {
  background: #93b7f3;
}

.divider {
  display: flex;
  align-items: center;
  width: 80%;
  margin: 10rpx 0 30rpx;
}

.line {
  flex: 1;
  height: 1rpx;
  background: #e0e0e0;
}

.or {
  margin: 0 24rpx;
  font-size: 24rpx;
  color: #aaa;
}

.guest-btn {
  width: 80%;
  height: 80rpx;
  line-height: 80rpx;
  background: #fff;
  color: #2563eb;
  font-size: 28rpx;
  border-radius: 40rpx;
  border: 1rpx solid #2563eb;
  margin-bottom: 40rpx;
}

.guest-btn[disabled] {
  color: #93b7f3;
  border-color: #93b7f3;
}

.hint {
  font-size: 24rpx;
  color: #999;
  margin-bottom: 8rpx;
}

.hint-guest {
  font-size: 22rpx;
  color: #bbb;
}
</style>
