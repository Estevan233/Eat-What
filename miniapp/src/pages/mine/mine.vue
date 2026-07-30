<template>
  <view class="page">
    <view v-if="userStore.isLoggedIn" class="logged-in">
      <image v-if="avatarUrl" class="avatar" :src="avatarUrl" mode="aspectFill" />
      <view v-else class="avatar avatar-placeholder">
        <text class="avatar-letter">{{ userStore.profile?.nickname?.charAt(0) || '?' }}</text>
      </view>
      <text class="nickname">{{ userStore.profile?.nickname || '微信用户' }}</text>
      <view class="badges">
        <text v-if="userStore.isGuest" class="badge badge-guest">游客</text>
        <text class="badge badge-id">id {{ userStore.profile?.id }}</text>
      </view>

      <view class="menu">
        <view class="menu-item" @click="goConstitution">
          <text class="menu-label">体质测试</text>
          <text v-if="userStore.hasConstitution" class="menu-value">已测 · {{ primaryLabel }}</text>
          <text v-else class="menu-action">未测，去测 →</text>
        </view>

        <view class="menu-item" @click="goProfile">
          <text class="menu-label">健康档案</text>
          <text v-if="userStore.hasProfile" class="menu-value">已填</text>
          <text v-else class="menu-action">未填，去填 →</text>
        </view>
      </view>

      <button v-if="userStore.isGuest" class="upgrade-btn" @click="goLogin">
        升级为正式账号
      </button>

      <button class="logout-btn" @click="onLogout">退出登录</button>
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
import { CONSTITUTION_NAMES } from '@/constants/constitution'

const userStore = useUserStore()

const avatarUrl = computed(() => userStore.profile?.avatar_url || '')
const primaryLabel = computed(() => {
  const c = userStore.constitution
  return c ? CONSTITUTION_NAMES[c.primary] : ''
})

function goLogin() {
  uni.navigateTo({
    url: '/pages/auth/auth?redirect=' + encodeURIComponent('/pages/mine/mine'),
  })
}

function goConstitution() {
  uni.switchTab({ url: '/pages/constitution/constitution' })
}

function goProfile() {
  uni.navigateTo({ url: '/pages/profile/profile' })
}

function onLogout() {
  uni.showModal({
    title: '确认退出',
    content: '退出后需要重新登录',
    success: (res) => {
      if (res.confirm) {
        userStore.clear()
        uni.showToast({ title: '已退出', icon: 'none' })
      }
    },
  })
}
</script>

<style lang="scss" scoped>
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 40rpx;
  min-height: 80vh;
}

.logged-in,
.not-logged-in {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
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

.badges {
  display: flex;
  gap: 12rpx;
  margin-bottom: 40rpx;
}

.badge {
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 24rpx;
  color: #888;
  background: #f0f0f0;
}

.badge-guest {
  color: #b45309;
  background: #fef3c7;
}

.badge-id {
  color: #aaa;
}

.menu {
  width: 100%;
  background: #fff;
  border-radius: 16rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
  margin-bottom: 30rpx;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-label {
  font-size: 30rpx;
  color: #1f2937;
}

.menu-value {
  font-size: 26rpx;
  color: #2563eb;
}

.menu-action {
  font-size: 26rpx;
  color: #888;
}

.upgrade-btn {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 40rpx;
  font-size: 28rpx;
  margin-bottom: 20rpx;
}

.logout-btn {
  width: 100%;
  height: 80rpx;
  line-height: 80rpx;
  background: #fff;
  color: #dc2626;
  border: 1rpx solid #dc2626;
  border-radius: 40rpx;
  font-size: 28rpx;
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
