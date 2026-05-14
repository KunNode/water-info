import { del, get, patch, post, withAuth } from './request'
import type {
  ConversationDetail,
  ConversationFullResponse,
  ConversationItem,
  FloodPlan,
  FloodSession,
  PageResponse,
  PlanApproveRequest,
  PlanApproveResponse,
  PlanAuditListResponse,
  PlanEditRequest,
  PlanExecuteResult,
  PlanProgressResponse,
} from '@/types'

export function queryFlood(data: { message: string; sessionId?: string; stream?: boolean }) {
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

export function getPlanProgress(id: string) {
  return get<PlanProgressResponse>(`/plans/${id}/progress`, undefined, withAuth())
}

export function updateActionStatus(planId: string, actionId: string, status: string) {
  return patch<{ plan_id: string; action_id: string; status: string }>(
    `/plans/${planId}/actions/${actionId}`,
    { status },
    withAuth(),
  )
}

export function cancelPlan(id: string) {
  return post<{ plan_id: string; status: string }>(`/plans/${id}/cancel`, undefined, withAuth())
}

export function updatePlan(id: string, body: PlanEditRequest) {
  return patch<FloodPlan>(`/plans/${id}`, body, withAuth())
}

export function approvePlan(id: string, body: PlanApproveRequest) {
  return post<PlanApproveResponse>(`/plans/${id}/approve`, body, withAuth())
}

export function getPlanAudits(id: string) {
  return get<PlanAuditListResponse>(`/plans/${id}/audits`, undefined, withAuth())
}

export function getSession(id: string) {
  return get<FloodSession>(`/sessions/${id}`, undefined, withAuth())
}

export function listConversations(params?: { limit?: number; offset?: number }) {
  return get<ConversationItem[]>('/conversations', params, withAuth())
}

export function getConversation(sessionId: string) {
  return get<ConversationFullResponse>(`/conversations/${sessionId}`, undefined, withAuth())
}

export function getConversationMessages(sessionId: string, params?: { limit?: number; beforeId?: number }) {
  return get<ConversationDetail>(`/conversations/${sessionId}/messages`, params, withAuth())
}

export function createConversation(title?: string) {
  return post<{ session_id: string; title: string; created_at: string }>(
    '/conversations',
    title ? { title } : {},
    withAuth(),
  )
}

export function renameConversation(sessionId: string, title: string) {
  return patch<{ session_id: string; title: string }>(`/conversations/${sessionId}`, { title }, withAuth())
}

export function deleteConversation(sessionId: string) {
  return del<{ message: string }>(`/conversations/${sessionId}`, withAuth())
}

// SSE streaming query - returns EventSource URL
export function getStreamUrl(baseUrl = ''): string {
  return `${baseUrl}/api/v1/flood/query/stream`
}
