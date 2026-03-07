import { get, post, put, del } from './request'
import type { ThresholdRule, CreateThresholdRuleRequest, ThresholdRuleQuery, PageResponse } from '@/types'

export function getThresholdRules(params: ThresholdRuleQuery) {
  return get<PageResponse<ThresholdRule>>('/threshold-rules', params)
}

export function getThresholdRule(id: string) {
  return get<ThresholdRule>(`/threshold-rules/${id}`)
}

export function createThresholdRule(data: CreateThresholdRuleRequest) {
  return post<ThresholdRule>('/threshold-rules', data)
}

export function updateThresholdRule(id: string, data: Partial<CreateThresholdRuleRequest>) {
  return put<ThresholdRule>(`/threshold-rules/${id}`, data)
}

export function enableThresholdRule(id: string) {
  return put<void>(`/threshold-rules/${id}/enable`)
}

export function disableThresholdRule(id: string) {
  return put<void>(`/threshold-rules/${id}/disable`)
}

export function deleteThresholdRule(id: string) {
  return del<void>(`/threshold-rules/${id}`)
}
