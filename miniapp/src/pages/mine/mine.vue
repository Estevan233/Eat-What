<template>
  <view class="page">
    <!-- 未登录 -->
    <view v-if="!userStore.isLoggedIn" class="not-logged-in">
      <image class="logo" src="/static/brand-avatar.png" mode="aspectFill" />
      <text class="title">未登录</text>
      <text class="subtitle">登录后可记录心情、收藏菜品、查看历史</text>
      <view class="btn-primary" @click="goLogin">
        <text class="btn-text">去登录</text>
      </view>
    </view>

    <!-- 已登录 -->
    <view v-else class="logged-in">
      <!-- 用户卡 -->
      <view class="user-card" @click="goAccountProfile">
        <image v-if="avatarUrl" class="avatar" :src="avatarUrl" mode="aspectFill" />
        <view v-else class="avatar avatar-placeholder">
          <text class="avatar-letter">{{ userStore.profile?.nickname?.charAt(0) || '?' }}</text>
        </view>
        <view class="user-info">
          <text class="nickname">{{ userStore.profile?.nickname || '微信用户' }}</text>
          <view class="badges">
            <text v-if="userStore.isGuest" class="badge badge-guest">游客</text>
          </view>
        </view>
      </view>

      <!-- 菜单 -->
      <view class="menu">
        <view class="menu-item" @click="goConstitution">
          <view class="menu-left">
            <uni-icons type="person" size="22" color="#e8590c" />
            <text class="menu-label">体质测试</text>
          </view>
          <text v-if="userStore.hasConstitution" class="menu-value">{{ primaryLabel }}</text>
          <text v-else class="menu-action">未测 ›</text>
        </view>
        <view class="menu-item" @click="goProfile">
          <view class="menu-left">
            <uni-icons type="star" size="22" color="#e8590c" />
            <text class="menu-label">健康档案</text>
          </view>
          <text v-if="userStore.hasProfile" class="menu-value">已填 ✓</text>
          <text v-else class="menu-action">未填 ›</text>
        </view>
        <view class="menu-item" @click="goFavorite">
          <view class="menu-left">
            <uni-icons type="heart" size="22" color="#e8590c" />
            <text class="menu-label">我的收藏</text>
          </view>
          <text class="menu-action">›</text>
        </view>
        <view class="menu-item" @click="goDiningMemory">
          <view class="menu-left">
            <uni-icons type="list" size="22" color="#e8590c" />
            <text class="menu-label">外食记录</text>
          </view>
          <text class="menu-action">›</text>
        </view>
      </view>

      <!-- 操作 -->
      <view v-if="userStore.isGuest" class="btn-upgrade" @click="goLogin">
        <text class="btn-upgrade-text">升级为正式账号</text>
      </view>
      <view class="btn-logout" @click="onLogout">
        <text class="btn-logout-text">退出登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { CONSTITUTION_NAMES } from '@/constants/constitution'
import type { ConstitutionResult } from '@/types/api'

const userStore = useUserStore()

const avatarUrl = computed(() => userStore.profile?.avatarUrl || '')
const primaryLabel = computed(() => {
  const c = userStore.constitution as ConstitutionResult | null
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

function goAccountProfile() {
  uni.navigateTo({
    url: '/pages/account-profile/account-profile?redirect=' + encodeURIComponent('/pages/mine/mine'),
  })
}

function goFavorite() {
  uni.navigateTo({ url: '/pages/favorite/favorite' })
}

function goDiningMemory() {
  uni.navigateTo({ url: '/pages/dining-memory/dining-memory' })
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
  min-height: 100vh;
  background: $bg;
  padding: 32rpx;
  box-sizing: border-box;
}

/* ---- 未登录 ---- */
.not-logged-in {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 160rpx;
}

.logo {
  width: 160rpx;
  height: 160rpx;
  border-radius: 44rpx;
  box-shadow: $shadow-cta;
  margin-bottom: 36rpx;
}

.title {
  font-size: 44rpx;
  font-weight: 700;
  color: $ink;
  margin-bottom: 16rpx;
}

.subtitle {
  font-size: 26rpx;
  color: $ink-2;
  margin-bottom: 64rpx;
  text-align: center;
}

.btn-primary {
  background: $grad-brand;
  border-radius: 999rpx;
  padding: 26rpx 120rpx;
  box-shadow: $shadow-cta;
}

.btn-text {
  color: #fff;
  font-size: 30rpx;
  font-weight: 700;
}

/* ---- 已登录 ---- */
.user-card {
  display: flex;
  align-items: center;
  gap: 28rpx;
  background: $card;
  border-radius: $radius-lg;
  padding: 36rpx 32rpx;
  box-shadow: $shadow-card;
  margin-bottom: 28rpx;
}

.avatar {
  width: 128rpx;
  height: 128rpx;
  border-radius: 40rpx;
}

.avatar-placeholder {
  background: $brand-light;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-letter {
  font-size: 52rpx;
  font-weight: 700;
  color: $brand;
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.nickname {
  font-size: 36rpx;
  font-weight: 700;
  color: $ink;
}

.badges {
  display: flex;
  gap: 12rpx;
}

.badge {
  font-size: 20rpx;
  padding: 4rpx 16rpx;
  border-radius: 24rpx;
}

.badge-guest {
  color: $warning;
  background: $warning-light;
}

/* ---- 菜单 ---- */
.menu {
  background: $card;
  border-radius: $radius-lg;
  box-shadow: $shadow-card;
  margin-bottom: 32rpx;
  overflow: hidden;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32rpx;
  border-bottom: 1rpx solid $line;

  &:active {
    background: $bg;
  }

  &:last-child {
    border-bottom: none;
  }
}

.menu-left {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.menu-label {
  font-size: 30rpx;
  color: $ink;
  font-weight: 600;
}

.menu-value {
  font-size: 26rpx;
  color: $fresh;
}

.menu-action {
  font-size: 26rpx;
  color: $ink-3;
}

/* ---- 操作按钮 ---- */
.btn-upgrade {
  border: 2rpx solid $brand-soft;
  background: $card;
  border-radius: 999rpx;
  padding: 26rpx 0;
  text-align: center;
  margin-bottom: 24rpx;
}

.btn-upgrade-text {
  color: $brand;
  font-size: 28rpx;
  font-weight: 600;
}

.btn-logout {
  border-radius: 999rpx;
  padding: 26rpx 0;
  text-align: center;
}

.btn-logout-text {
  color: $danger;
  font-size: 28rpx;
}
</style>
