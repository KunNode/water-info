import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, clearAuth } from '@/utils/storage'
import router from '@/router'
import type { ApiResponse } from '@/types'

const service: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

function resolveAuthorizationHeader(config?: AxiosRequestConfig | InternalAxiosRequestConfig): string | undefined {
  const headers = config?.headers as Record<string, unknown> | undefined
  const value = headers?.Authorization ?? headers?.authorization
  return typeof value === 'string' ? value : undefined
}

function handleUnauthorized(config?: AxiosRequestConfig | InternalAxiosRequestConfig) {
  const storedToken = getToken()
  const sentAuthorization = resolveAuthorizationHeader(config)

  // If the client still has a token but this request went out without Authorization,
  // avoid clearing the whole session because that usually indicates a client-side race
  // or a missing header on a single request rather than an expired login.
  if (storedToken && !sentAuthorization) {
    ElMessage.error('请求未携带登录凭证，请刷新页面后重试')
    return
  }

  clearAuth()
  router.push('/login')
  ElMessage.error('登录已过期，请重新登录')
}

// Request interceptor — attach JWT token
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — unwrap ApiResponse, handle errors
service.interceptors.response.use(
  (response) => {
    const res = response.data as ApiResponse
    if (res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      if (res.code === 401) {
        handleUnauthorized(response.config)
      }
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return response.data
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        handleUnauthorized(error.config)
      } else if (status === 403) {
        ElMessage.error('没有操作权限')
      } else if (status === 404) {
        ElMessage.error('请求的资源不存在')
      } else if (status >= 500) {
        ElMessage.error('服务器异常，请稍后重试')
      } else {
        ElMessage.error(error.response.data?.message || '请求失败')
      }
    } else {
      ElMessage.error('网络连接异常')
    }
    return Promise.reject(error)
  },
)

// Typed request helpers
export function get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
  return service.get(url, { params, ...config }) as any
}

export function post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
  return service.post(url, data, config) as any
}

export function put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
  return service.put(url, data, config) as any
}

export function del<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
  return service.delete(url, config) as any
}

export function withAuth(config: AxiosRequestConfig = {}): AxiosRequestConfig {
  const token = getToken()
  const headers = {
    ...(config.headers as Record<string, unknown> | undefined),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
  return { ...config, headers }
}

export default service
