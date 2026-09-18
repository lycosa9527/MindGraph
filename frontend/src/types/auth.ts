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
 * - student: Classroom Learning Space student (学生账号)
 * - personal_trial: C-end trial account (体验版)
 * - personal_paid: C-end paid account (超级会员)
 */
export type UserRole =
  | 'superadmin'
  | 'platform_bd'
  | 'expert'
  | 'school_admin'
  | 'teacher'
  | 'student'
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

export interface DailyTokensSummary {
  cap: number
  usedToday: number
  remainingToday: number
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
  /** Dual-language UI chrome (buttons / tooltips / modal chrome) */
  bilingualUiEnabled?: boolean
  /** Presenter locale for the smaller bilingual line */
  presenterUiLocale?: string | null
  /** Persisted UI version (chinese | international); absent until loaded from server */
  uiVersion?: string | null
  /** Persisted AI generate audience (学段); null = unset */
  educationStage?: string | null
  /** Persisted mind-map 专业程度 id; null = unset (defaults to general) */
  aiContentLevel?: string | null
  /** V3 ribbon classic (full) height; false / unset = simplified */
  v3RibbonClassic?: boolean
  /** Last V3 ribbon tab id (file|home|design|review|ai) */
  v3RibbonTab?: string | null
  /** New-canvas classroom remote is open; unset defaults to visible */
  classroomRemoteVisible?: boolean
  /** False for overseas email accounts: Simplified Chinese (`zh`) UI is not available */
  allowsSimplifiedChinese?: boolean
  /** False for quick-registration users until they set a known password (SMS) */
  loginPasswordSet?: boolean
  /** Student Learning Space: force password change after initial login */
  mustChangePassword?: boolean
  /** Student Learning Space class id */
  learningClassId?: number | null
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
  /** Per-user daily LLM token budget from /me */
  dailyTokens?: DailyTokensSummary
  /** School custom native LLM is active */
  customLlmEnabled?: boolean
  /** School model name shown on the canvas */
  customLlmModel?: string | null
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
        custom_llm_enabled?: boolean
        custom_llm_model?: string | null
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
  bilingual_ui_enabled?: boolean
  presenter_ui_locale?: string | null
  education_stage?: string | null
  ai_content_level?: string | null
  v3_ribbon_classic?: boolean | null
  v3_ribbon_tab?: string | null
  classroom_remote_visible?: boolean | null
  classroomRemoteVisible?: boolean | null
  allows_simplified_chinese?: boolean
  login_password_set?: boolean
  must_change_password?: boolean
  learning_class_id?: number | null
  thinking_coins?: {
    balance?: number
    eligible?: boolean
  }
  daily_tokens?: {
    cap?: number
    used_today?: number
    remaining_today?: number
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

export interface StudentLoginCredentials {
  class_code: string
  name: string
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
  code?: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  mode: AuthMode
  loading: boolean
}

export interface SessionStatus {
  status: 'active' | 'invalidated' | 'unauthenticated'
  message?: string
  reason?: string
}
