import { get, post, put, del } from './request'
import type { Station, CreateStationRequest, UpdateStationRequest, StationQuery, PageResponse } from '@/types'

export function getStations(params: StationQuery) {
  return get<PageResponse<Station>>('/stations', params)
}

export function getStation(id: string) {
  return get<Station>(`/stations/${id}`)
}

export function createStation(data: CreateStationRequest) {
  return post<Station>('/stations', data)
}

export function updateStation(id: string, data: UpdateStationRequest) {
  return put<Station>(`/stations/${id}`, data)
}

export function deleteStation(id: string) {
  return del<void>(`/stations/${id}`)
}
