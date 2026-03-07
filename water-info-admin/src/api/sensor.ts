import { get, post, put, del } from './request'
import type { Sensor, CreateSensorRequest, SensorQuery, PageResponse } from '@/types'

export function getSensors(params: SensorQuery) {
  return get<PageResponse<Sensor>>('/sensors', params)
}

export function getSensor(id: string) {
  return get<Sensor>(`/sensors/${id}`)
}

export function createSensor(data: CreateSensorRequest) {
  return post<Sensor>('/sensors', data)
}

export function updateSensor(id: string, data: Partial<CreateSensorRequest>) {
  return put<Sensor>(`/sensors/${id}`, data)
}

export function updateSensorStatus(id: string, status: string) {
  return put<Sensor>(`/sensors/${id}/status`, null, { params: { status } })
}

export function deleteSensor(id: string) {
  return del<void>(`/sensors/${id}`)
}
