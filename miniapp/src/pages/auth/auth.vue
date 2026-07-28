<template>
  <view class="page">
    <view class="hero">
      <text class="title">今天吃啥</text>
      <text class="subtitle">用星座、节气、天气、心情、体质告诉你今天该吃啥</text>
    </view>

    <button class="login-btn" :disabled="loading" @click="onLogin">
      {{ loading ? '登录中…' : '微信一键登录' }}
    </button>

    <text class="hint">登录后才能记录心情、收藏菜品、查看历史</text>
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

    // 从 query 取 redirect，没有就回 today tab
    const pages = getCurrentPages()
    const current = pages[pages.length - 1] as { options?: { redirect?: string } }
    const redirect = current?.options?.redirect

    if (redirect) {
      uni.redirectTo({ url: decodeURIComponent(redirect) })
    } else {
      uni.switchTab({ url: '/pages/today/today' })
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : '登录失败'
    uni.showToast({ title: msg, icon: 'none' })
  } finally {
    loading.value = false
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

.hint {
  font-size: 24rpx;
  color: #999;
}
</style>
