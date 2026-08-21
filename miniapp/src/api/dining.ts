import { request } from './request'
import type {
  DiningMemoryList,
  DiningMemoryRead,
  DiningMemoryUpsert,
  DiningVerdict,
  ExternalDiningRequest,
  ExternalDiningResponse,
} from '@/types/api'

export const recommendExternal = (
  data: ExternalDiningRequest,
): Promise<ExternalDiningResponse> =>
  request<ExternalDiningResponse, ExternalDiningRequest>({
    url: '/api/v1/dining/recommend',
    method: 'POST',
    data,
    loading: false,
  })

export const listDiningMemories = (
  page = 1,
  size = 20,
  verdict?: DiningVerdict,
): Promise<DiningMemoryList> => {
  const verdictQuery = verdict ? `&verdict=${verdict}` : ''
  return request<DiningMemoryList>({
    url: `/api/v1/dining/memories?page=${page}&size=${size}${verdictQuery}`,
  })
}

export const upsertDiningMemory = (
  data: DiningMemoryUpsert,
): Promise<DiningMemoryRead> =>
  request<DiningMemoryRead, DiningMemoryUpsert>({
    url: '/api/v1/dining/memories',
    method: 'PUT',
    data,
  })

export const deleteDiningMemory = (
  memoryId: number,
): Promise<{ deleted: boolean }> =>
  request<{ deleted: boolean }>({
    url: `/api/v1/dining/memories/${memoryId}`,
    method: 'DELETE',
  })
