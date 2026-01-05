/**
 * Auth Types - Type definitions for authentication
 */

export type AuthMode = 'standard' | 'demo' | 'bayi' | 'enterprise'

/**
 * User roles hierarchy:
 * - user: Regular user (default)
 * - manager: Organization manager - can access org-scoped admin dashboard
 * - admin: Full admin access to all organizations
 * - superadmin: Reserved for future use (currently same as admin)
 */
export type UserRole = 'user' | 'manager' | 'admin' | 'superadmin'

export interface User {
  id: string
  username: string
  phone?: string
  email?: string
  role: UserRole
  schoolId?: string
  schoolName?: string
  avatar?: string
  createdAt?: string
  lastLogin?: string
}

export interface LoginCredentials {
  phone?: string
  username?: string
  password: string
  captcha?: string
  captcha_id?: string
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
