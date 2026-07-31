/**
 * 位置授权组合式函数 - 包装 wx.getLocation 为 Promise，处理拒绝授权。
 *
 * 学习点：
 * - 微信小程序 wx.getLocation 需用户已授权 scope.userLocation
 * - 拒绝授权时 wx.getLocation fail 回调带 errMsg 含 "auth deny"
 * - 用 ref 暴露 permissionDenied 状态，UI 给重新授权引导
 * - 重新授权需调 uni.openSetting 引导用户打开开关
 */
import { ref } from 'vue'

export interface Coords {
  lat: number
  lng: number
}

export function useLocation() {
  const permissionDenied = ref(false)
  const locating = ref(false)
  const errMsg = ref<string>('')

  /**
   * 拿当前位置坐标。已授权时 resolve(coords)，拒绝 reject(Error)。
   */
  function getLocation(): Promise<Coords> {
    locating.value = true
    errMsg.value = ''
    return new Promise<Coords>((resolve, reject) => {
      uni.getLocation({
        type: 'wgs84',
        success: (res) => {
          permissionDenied.value = false
          // 微信返回 latitude/longitude（驼峰）
          if (typeof res.latitude === 'number' && typeof res.longitude === 'number') {
            resolve({ lat: res.latitude, lng: res.longitude })
          } else {
            reject(new Error('未拿到经纬度'))
          }
        },
        fail: (err) => {
          const msg = err.errMsg || '获取位置失败'
          // 微信拒绝授权时 errMsg 含 "auth deny" 或 "deny"
          if (msg.includes('auth deny') || msg.includes('deny')) {
            permissionDenied.value = true
          }
          errMsg.value = msg
          reject(new Error(msg))
        },
        complete: () => {
          locating.value = false
        },
      })
    })
  }

  /**
   * 引导用户打开位置授权。调起系统授权设置页，用户回来后会通过 success/fail
   * 告诉我们用户是否勾选了。
   */
  function requestPermission(): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      uni.openSetting({
        success: (res) => {
          // res.authSetting['scope.userLocation'] === true 表示已重新授权
          const granted = !!res.authSetting?.['scope.userLocation']
          if (granted) {
            permissionDenied.value = false
          }
          resolve(granted)
        },
        fail: () => resolve(false),
      })
    })
  }

  return {
    permissionDenied,
    locating,
    errMsg,
    getLocation,
    requestPermission,
  }
}