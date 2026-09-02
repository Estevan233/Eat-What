import { request } from './request'
import type {
  CitySpecialtiesResponse,
  DiningMemoryList,
  DiningMemoryRead,
  DiningMemoryUpsert,
  DiningVerdict,
  ExternalDiningRequest,
  ExternalDiningResponse,
} from '@/types/api'

export type { DiningMemoryRead }

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
  query = '',
  date?: string,
): Promise<DiningMemoryList> => {
  const verdictQuery = verdict ? `&verdict=${verdict}` : ''
  const queryQuery = query.trim() ? `&query=${encodeURIComponent(query.trim())}` : ''
  const dateQuery = date ? `&date=${encodeURIComponent(date)}` : ''
  return request<DiningMemoryList>({
    url: `/api/v1/dining/memories?page=${page}&size=${size}${verdictQuery}${queryQuery}${dateQuery}`,
    loading: false,
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

export const getCitySpecialties = (city: string): Promise<CitySpecialtiesResponse> =>
  request<CitySpecialtiesResponse>({
    url: `/api/v1/dining/specialties?city=${encodeURIComponent(city.trim())}`,
    method: 'GET',
    loading: false,
  })
