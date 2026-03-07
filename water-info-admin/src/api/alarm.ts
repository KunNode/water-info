import { get, post } from './request'
import type { Alarm, AlarmQuery, PageResponse } from '@/types'

export function getAlarms(params: AlarmQuery) {
  return get<PageResponse<Alarm>>('/alarms', params)
}

export function getAlarm(id: string) {
  return get<Alarm>(`/alarms/${id}`)
}

export function ackAlarm(id: string) {
  return post<Alarm>(`/alarms/${id}/ack`)
}

export function closeAlarm(id: string) {
  return post<Alarm>(`/alarms/${id}/close`)
}
