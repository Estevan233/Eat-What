<template>
  <view class="page">
    <view v-if="userStore.isLoggedIn" class="logged-in">
      <image v-if="avatarUrl" class="avatar" :src="avatarUrl" mode="aspectFill" />
      <view v-else class="avatar avatar-placeholder">
        <text class="avatar-letter">{{ userStore.profile?.nickname?.charAt(0) || '?' }}</text>
      </view>
      <text class="nickname">{{ userStore.profile?.nickname || '微信用户' }}</text>
      <text class="hint">登录态有效 · id {{ userStore.profile?.id }}</text>
    </view>

    <view v-else class="not-logged-in">
      <text class="title">未登录</text>
      <text class="subtitle">登录后可记录心情、收藏菜品、查看历史</text>
      <button class="login-btn" @click="goLogin">去登录</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const avatarUrl = computed(() => userStore.profile?.avatar_url || '')

function goLogin() {
  uni.navigateTo({ url: '/pages/auth/auth?redirect=' + encodeURIComponent('/pages/mine/mine') })
}
</script>

<style lang="scss" scoped>
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
  padding: 40rpx;
}

.logged-in,
.not-logged-in {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.avatar {
  width: 160rpx;
  height: 160rpx;
  border-radius: 80rpx;
  margin-bottom: 30rpx;
}

.avatar-placeholder {
  background: #e8edf5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-letter {
  font-size: 64rpx;
  font-weight: 600;
  color: #2563eb;
}

.nickname {
  font-size: 40rpx;
  font-weight: 600;
  color: #333;
  margin-bottom: 16rpx;
}

.hint {
  font-size: 24rpx;
  color: #999;
}

.title {
  font-size: 48rpx;
  font-weight: 600;
  color: #2563eb;
  margin-bottom: 20rpx;
}

.subtitle {
  font-size: 26rpx;
  color: #888;
  margin-bottom: 60rpx;
  text-align: center;
}

.login-btn {
  background: #2563eb;
  color: #fff;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 30rpx;
  border-radius: 40rpx;
  border: none;
  padding: 0 60rpx;
}
</style>
