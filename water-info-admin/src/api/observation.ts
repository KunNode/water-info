import { get } from './request'
import type { Observation, ObservationQuery, PageResponse } from '@/types'

export function getObservations(params: ObservationQuery) {
  return get<PageResponse<Observation>>('/observations', params)
}

export function getLatestObservation(stationId: string, metricType: string) {
  return get<Observation>('/observations/latest', { stationId, metricType })
}
