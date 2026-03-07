import { get, post, put, del } from './request'
import type { User, CreateUserRequest, UserQuery, Role, Org, CreateOrgRequest, Dept, CreateDeptRequest, AuditLog, AuditLogQuery, PageResponse } from '@/types'

// ─── User ───
export function getUsers(params: UserQuery) {
  return get<PageResponse<User>>('/users', params)
}

export function getUser(id: string) {
  return get<User>(`/users/${id}`)
}

export function createUser(data: CreateUserRequest) {
  return post<User>('/users', data)
}

export function updateUser(id: string, data: Partial<CreateUserRequest>) {
  return put<User>(`/users/${id}`, data)
}

export function changePassword(id: string, data: { oldPassword?: string; newPassword: string }) {
  return put<void>(`/users/${id}/password`, data)
}

export function setUserRoles(id: string, roleIds: string[]) {
  return put<void>(`/users/${id}/roles`, { roleIds })
}

export function deleteUser(id: string) {
  return del<void>(`/users/${id}`)
}

// ─── Role ───
export function getRoles(params?: { page?: number; size?: number }) {
  return get<PageResponse<Role>>('/roles', params)
}

export function getRole(id: string) {
  return get<Role>(`/roles/${id}`)
}

// ─── Org ───
export function getOrgs(params?: { page?: number; size?: number; keyword?: string }) {
  return get<PageResponse<Org>>('/orgs', params)
}

export function getOrg(id: string) {
  return get<Org>(`/orgs/${id}`)
}

export function createOrg(data: CreateOrgRequest) {
  return post<Org>('/orgs', data)
}

export function updateOrg(id: string, data: Partial<CreateOrgRequest>) {
  return put<Org>(`/orgs/${id}`, data)
}

export function deleteOrg(id: string) {
  return del<void>(`/orgs/${id}`)
}

// ─── Dept ───
export function getDepts(params?: { page?: number; size?: number; orgId?: string }) {
  return get<PageResponse<Dept>>('/depts', params)
}

export function getDept(id: string) {
  return get<Dept>(`/depts/${id}`)
}

export function createDept(data: CreateDeptRequest) {
  return post<Dept>('/depts', data)
}

export function updateDept(id: string, data: Partial<CreateDeptRequest>) {
  return put<Dept>(`/depts/${id}`, data)
}

export function deleteDept(id: string) {
  return del<void>(`/depts/${id}`)
}

// ─── AuditLog ───
export function getAuditLogs(params: AuditLogQuery) {
  return get<PageResponse<AuditLog>>('/audit-logs', params)
}
