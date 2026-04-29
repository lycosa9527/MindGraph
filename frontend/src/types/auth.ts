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
  /** Persisted UI locale (zh | en | az); absent until loaded from server */
  uiLanguage?: string | null
  /** Persisted prompt output language code; absent until loaded from server */
  promptLanguage?: string | null
  /** Persisted prompt/UI sync: when true, assistant language follows interface */
  matchPromptToUi?: boolean
  /** Persisted UI version (chinese | international); absent until loaded from server */
  uiVersion?: string | null
  /** False for overseas email accounts: Simplified Chinese (`zh`) UI is not available */
  allowsSimplifiedChinese?: boolean
  /** False for quick-registration users until they set a known password (SMS) */
  loginPasswordSet?: boolean
}

/**
 * Backend user response format - the raw format returned by the API
 * This differs from the frontend User interface and needs normalization
 */
export interface BackendUser {
  id?: string | number
  name?: string
  username?: string
  phone?: string
  email?: string
  role?: UserRole
  avatar?: string
  organization?: string | { id?: string | number; name?: string; display_name?: string }
  schoolId?: string
  schoolName?: string
  created_at?: string
  createdAt?: string
  last_login?: string
  lastLogin?: string
  ui_language?: string | null
  prompt_language?: string | null
  ui_version?: string | null
  match_prompt_to_ui?: boolean
  allows_simplified_chinese?: boolean
  login_password_set?: boolean
  user?: {
    id?: string | number
    phone?: string
  }
}

export interface LoginCredentials {
  phone?: string
  email?: string
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
