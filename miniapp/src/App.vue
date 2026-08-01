<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

onLaunch(() => {
  console.log('App 启动，token 存在？', userStore.isLoggedIn)
})

onShow(() => {
  uni.onNetworkStatusChange((res) => {
    if (!res.isConnected) {
      uni.showToast({ title: '网络断开', icon: 'none' })
    }
  })
})
</script>

<style lang="scss">
/* 全局 reset - 品牌暖色系 */
page {
  background-color: $bg;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
  font-size: 28rpx;
  color: $ink;
}

/* 通用工具类 */
.flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
