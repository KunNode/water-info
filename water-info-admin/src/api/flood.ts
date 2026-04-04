import { get, post, withAuth } from './request'
import type { FloodPlan, FloodSession, PageResponse, PlanExecuteResult } from '@/types'

export function queryFlood(data: { query: string; sessionId?: string }) {
  return post<any>('/flood/query', data, withAuth())
}

export function getPlans(params?: { page?: number; size?: number }) {
  return get<PageResponse<FloodPlan>>('/plans', params, withAuth())
}

export function getPlan(id: string) {
  return get<FloodPlan>(`/plans/${id}`, undefined, withAuth())
}

export function executePlan(id: string) {
  return post<PlanExecuteResult>(`/plans/${id}/execute`, undefined, withAuth())
}

export function getSession(id: string) {
  return get<FloodSession>(`/sessions/${id}`, undefined, withAuth())
}

// SSE streaming query - returns EventSource URL
export function getStreamUrl(baseUrl = ''): string {
  return `${baseUrl}/api/v1/flood/query/stream`
}
