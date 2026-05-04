import { get, post, put, patch, del } from './request'
import type {
  CreateDispatchRequest,
  CreateResourceRequest,
  DispatchQuery,
  PageResponse,
  Resource,
  ResourceDispatch,
  ResourceQuery,
  ResourceStats,
  UpdateDispatchStatusRequest,
  UpdateResourceRequest,
} from '@/types'

export function getResources(params: ResourceQuery) {
  return get<PageResponse<Resource>>('/resources', params)
}

export function getResource(id: string) {
  return get<Resource>(`/resources/${id}`)
}

export function createResource(data: CreateResourceRequest) {
  return post<Resource>('/resources', data)
}

export function updateResource(id: string, data: UpdateResourceRequest) {
  return put<Resource>(`/resources/${id}`, data)
}

export function deleteResource(id: string) {
  return del<void>(`/resources/${id}`)
}

export function getResourceStats() {
  return get<ResourceStats[]>('/resources/stats')
}

export function getAvailableResources(params?: { type?: string; location?: string }) {
  return get<Resource[]>('/resources/available', params)
}

export function getDispatches(params: DispatchQuery) {
  return get<PageResponse<ResourceDispatch>>('/resource-dispatches', params)
}

export function getDispatch(id: string) {
  return get<ResourceDispatch>(`/resource-dispatches/${id}`)
}

export function createDispatch(data: CreateDispatchRequest) {
  return post<ResourceDispatch>('/resource-dispatches', data)
}

export function updateDispatchStatus(id: string, data: UpdateDispatchStatusRequest) {
  return patch<ResourceDispatch>(`/resource-dispatches/${id}/status`, data)
}
