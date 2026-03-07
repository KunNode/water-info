// API response types matching backend ApiResponse<T>
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
  traceId: string
  timestamp: number
  pagination?: Pagination
  metadata?: Record<string, any>
}

export interface Pagination {
  page: number
  size: number
  total: number
  pages: number
}

export interface PageParams {
  page?: number
  size?: number
}

export interface PageResponse<T> {
  records: T[]
  total: number
  page: number
  size: number
  pages: number
}
