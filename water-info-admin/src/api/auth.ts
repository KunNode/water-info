import { post, get } from './request'
import type { LoginRequest, LoginResponse, UserInfo } from '@/types'

export function login(data: LoginRequest) {
  return post<LoginResponse>('/auth/login', data)
}

export function getMe() {
  return get<UserInfo>('/auth/me')
}

export function logout() {
  return post<void>('/auth/logout')
}
