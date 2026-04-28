import { get } from './request'
import type { AiAssessment } from '@/types'

export function getAiAssessments(params?: { stationId?: string; since?: string; limit?: number }) {
  return get<AiAssessment[]>('/ai-assessments', params)
}
