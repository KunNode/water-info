import { get, post, patch, del, withAuth } from './request'
import type { ConversationDetail, ConversationFullResponse, ConversationItem, FloodPlan, FloodSession, PageResponse, PlanExecuteResult } from '@/types'

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

export function updatePlanStatus(id: string, status: string) {
  return patch<{ plan_id: string; status: string }>(`/plans/${id}/status`, { status }, withAuth())
}

export function getSession(id: string) {
  return get<FloodSession>(`/sessions/${id}`, undefined, withAuth())
}

// ── Conversation (session with memory) ──────────────────────────────────────

export function listConversations(params?: { limit?: number; offset?: number }) {
  return get<ConversationItem[]>('/conversations', params, withAuth())
}

/**
 * Get conversation metadata and snapshot (for session recovery without messages).
 */
export function getConversation(sessionId: string) {
  return get<ConversationFullResponse>(`/conversations/${sessionId}`, undefined, withAuth())
}

/**
 * Get messages for a conversation with optional cursor-based pagination.
 */
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
