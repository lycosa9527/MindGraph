/**
 * Auth Types - Type definitions for authentication
 */

export type AuthMode = 'standard' | 'bayi' | 'enterprise'

/**
 * User roles (canonical DB slugs):
 * - superadmin: Full platform admin (超级管理员)
 * - platform_bd: Teaching researcher — read-only global dashboard (教研员)
 * - expert: Platform expert — B2B school invites (own orgs) (专家)
 * - school_admin: Organization manager — own-school dashboard + user mgmt (学校管理员)
 * - teacher: B2B school member (教师用户 / 学校版)
 * - personal_trial: C-end trial account (体验版)
 * - personal_paid: C-end paid account (超级会员)
 */
export type UserRole =
  | 'superadmin'
  | 'platform_bd'
  | 'expert'
  | 'school_admin'
  | 'teacher'
  | 'personal_trial'
  | 'personal_paid'

/** Legacy role slugs still accepted during rollout window */
export type LegacyUserRole = 'user' | 'manager' | 'admin'

export type AnyUserRole = UserRole | LegacyUserRole

export type SchoolTier = 'trial' | 'lite' | 'standard' | 'professional'

export interface SchoolTierFeatures {
  online_collab: boolean
  chrome_extension: boolean
  presentation_tools: boolean
  api_token: boolean
}

export interface ThinkingCoinsSummary {
  balance: number
  eligible: boolean
}

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
  /** Per-school MindMate sidebar label when configured by admin */
  mindmateAgentName?: string | null
  /** Per-school MindMate avatar URL when configured by admin */
  mindmateAgentAvatarUrl?: string | null
  /** B2B school subscription tier (trial | lite | standard | professional) */
  schoolTier?: SchoolTier | null
  /** Tier-gated feature flags from login /me organization payload */
  schoolTierFeatures?: SchoolTierFeatures | null
  /** True when the school contract end date has passed (tier downgraded to trial) */
  subscriptionExpired?: boolean
  /** Trial-teacher thinking coin wallet summary from /me */
  thinkingCoins?: ThinkingCoinsSummary
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
  role?: AnyUserRole
  avatar?: string
  organization?:
    | string
    | {
        id?: string | number
        name?: string
        display_name?: string
        mindmate_agent_name?: string | null
        mindmate_agent_avatar_url?: string | null
        school_tier?: string | null
        school_tier_features?: SchoolTierFeatures | null
        subscription_expired?: boolean
      }
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
  thinking_coins?: {
    balance?: number
    eligible?: boolean
  }
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
