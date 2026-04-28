import { get, post } from './request'
import type { MetricType, Observation, ObservationQuery, PageResponse } from '@/types'

export interface LatestObservationBatchItem {
  stationId: string
  metricType: MetricType
}

export function getObservations(params: ObservationQuery) {
  return get<PageResponse<Observation>>('/observations', params)
}

export function getLatestObservation(stationId: string, metricType: string) {
  return get<Observation>('/observations/latest', { stationId, metricType })
}

export function getLatestObservations(items: LatestObservationBatchItem[]) {
  return post<Observation[]>('/observations/latest/batch', { items })
}
