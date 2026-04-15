import { get, post } from './request'
import type { FloodPlan, PageResponse } from '@/types'

export function queryFlood(data: { query: string; sessionId?: string }) {
  return post<any>('/flood/query', data)
}

export function getPlans(params?: { page?: number; size?: number }) {
  return get<PageResponse<FloodPlan>>('/plans', params)
}

export function getPlan(id: string) {
  return get<FloodPlan>(`/plans/${id}`)
}

export function executePlan(id: string) {
  return post<FloodPlan>(`/plans/${id}/execute`)
}

export function getSession(id: string) {
  return get<any>(`/sessions/${id}`)
}

// SSE streaming query - returns EventSource URL
export function getStreamUrl(baseUrl = ''): string {
  return `${baseUrl}/api/v1/flood/query/stream`
}
