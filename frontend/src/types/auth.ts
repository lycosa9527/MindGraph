/**
 * Auth Types - Type definitions for authentication
 */

export type AuthMode = 'standard' | 'demo' | 'bayi' | 'enterprise'

export interface User {
  id: string
  username: string
  email?: string
  role: 'user' | 'admin' | 'superadmin'
  schoolId?: string
  schoolName?: string
  createdAt?: string
  lastLogin?: string
}

export interface LoginCredentials {
  phone: string
  password: string
  captcha: string
  captcha_id: string
}

export interface CaptchaResponse {
  captcha_id: string
  captcha_image: string
}

export interface LoginResponse {
  success: boolean
  token?: string
  user?: User
  message?: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  mode: AuthMode
  loading: boolean
}

export interface SessionStatus {
  status: 'valid' | 'invalidated' | 'expired'
  message?: string
}
