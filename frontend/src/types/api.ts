/**
 * API Types - Type definitions for API requests/responses
 */

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export interface ApiError {
  status: number
  message: string
  code?: string
}

export interface HealthResponse {
  status: string
  version: string
  uptime: number
}

export interface GenerateRequest {
  prompt: string
  diagramType: string
  sessionId?: string
}

export interface GenerateResponse {
  sessionId: string
  diagramData: Record<string, unknown>
  message?: string
}

export interface SSEMessage {
  event: string
  data: unknown
  id?: string
}
