/**
 * 附近店铺 API - 地图选点后的附近 POI 参考。
 *
 * 学习点：
 * - /nearby/shops 需登录（防滥用），POST body 为 gcj02 坐标（与 wx.chooseLocation 返回一致）
 * - providerAvailable=false 表示服务未开启/配额耗尽/上游失败，前端降级提示而不是展示空列表
 * - 锚点仅当次使用不落库（PRD R6）；服务端已做网格缓存节流（个人配额 200 次/日）
 */
import { request } from './request'
import type { NearbyShopsRequest, NearbyShopsResponse } from '@/types/api'

export const searchNearbyShops = (data: NearbyShopsRequest) =>
  request<NearbyShopsResponse, NearbyShopsRequest>({
    url: '/api/v1/nearby/shops',
    method: 'POST',
    data,
    loading: false,
  })
