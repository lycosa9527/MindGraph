/**
 * Auth Store - Pinia store for authentication state
 *
 * Security: Tokens are stored in httpOnly cookies, not accessible to JavaScript.
 * Only user metadata is stored in sessionStorage for UI display.
 *
 * Token Flow:
 * - Access tokens (1 hour) stored in httpOnly cookie, auto-refreshed via refresh token
 * - Refresh tokens (7 days) stored in httpOnly cookie with restricted path
 * - User data stored in sessionStorage (cleared on browser close)
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import { difyKeys } from '@/composables/queries/difyKeys'
import { isEducationStage } from '@/constants/educationStage'
import { i18n } from '@/i18n'
import { isPromptOutputLanguageCode, isUiLocale } from '@/i18n/locales'
import { useAiContentLevelStore } from '@/stores/aiContentLevel'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useMindMateStore } from '@/stores/mindmate'
import { useShowcaseStore } from '@/stores/showcase'
import { useUIStore } from '@/stores/ui'
import type { Language, PromptLanguage } from '@/stores/ui'
import type {
  AuthMode,
  BackendUser,
  CaptchaResponse,
  LoginCredentials,
  LoginResponse,
  User,
  UserRole,
} from '@/types'
import {
  type AdminCapabilitiesPayload,
  canAccessZhihui as capsIncludeZhihui,
  hasSuperadminPanelAccess,
  roleHasPanelAccess,
} from '@/utils/adminCapabilities'
import { registerAiContentLevelAuthBridge } from '@/utils/aiContentLevelAuthBridge'
import { getAppQueryClient } from '@/utils/appQueryClient'
import { getSafePostAuthPath } from '@/utils/authRedirect'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { normalizeAuthUser } from '@/utils/normalizeAuthUser'
import { clearSavedLoginCredentials } from '@/utils/savedLoginCredentials'
import {
  ensureFreshSessionAfterAuthFailure,
  getSessionRefreshEpoch,
  refreshSessionAccessToken,
} from '@/utils/sessionRefresh'
import { normalizeUserRole } from '@/utils/userRoleDisplay'
import { clearWorkshopChatCachesForUser } from '@/utils/workshopChatLocalCache'
import {
  disconnectWorkshopChatWsIfAny,
  resetWorkshopChatOnAuthClear,
} from '@/utils/workshopChatWsRegistry'

// User data stored in sessionStorage (not tokens - those are in httpOnly cookies)
const USER_KEY = 'auth_user'
const MODE_KEY = 'auth_mode'
const API_BASE = '/api/auth'

export const useAuthStore = defineStore('auth', () => {
  /** App QueryClient from main.ts — safe outside setup/injection context. */
  function getQueryClient() {
    return getAppQueryClient()
  }

  // Helper to get translated message
  function getTranslatedMessage(key: string): string {
    return i18n.global.t(key) as string
  }

  // State
  const user = ref<User | null>(null)
  // Token is no longer stored in JavaScript - it's in httpOnly cookies
  // This ref is kept for backward compatibility but should not be relied upon
  const token = ref<string | null>(null)
  const mode = ref<AuthMode>('standard')
  /** From GET /api/auth/mode; signup UI gated when false. Defaults true until the server responds. */
  const registrationEnabled = ref(true)
  const loading = ref(false)
  const sessionMonitorInterval = ref<number | null>(null)
  const showSessionExpiredModal = ref(false)
  const sessionExpiredMessage = ref('')
  const pendingRedirect = ref<string | null>(null) // Store intended route after session expired login
  const isCheckingAuth = ref(false) // Prevent duplicate concurrent checkAuth calls
  const lastSessionCheckTime = ref<number>(0) // Track last session status check to prevent rapid-fire calls
  const adminCapabilitiesPayload = ref<AdminCapabilitiesPayload | null>(null)
  const adminCapabilitiesLoaded = ref(false)
  const lastProfileRefreshTime = ref<number>(0)
  const lastAdminCapabilitiesFetchTime = ref<number>(0)
  const hasVerifiedAuthThisSession = ref(false) // Track if we've verified auth with server in this session
  const PROFILE_REFRESH_MIN_MS = 30_000
  const SESSION_KICK_POLL_MS = 120_000
  const ADMIN_CAPABILITIES_CACHE_MS = 60_000
  let profileVisibilityListener: (() => void) | null = null
  /**
   * True when the last /me (or refresh) attempt failed before an HTTP status was obtained
   * (network offline, DNS, aborted request, etc.) while a cached user still exists.
   * Guards treat checkAuth as success so users are not sent to /auth while offline; the next
   * checkAuth retry clears this once the server responds.
   */
  const authVerificationBlockedByNetwork = ref(false)
  /** Avoid duplicate PATCH when seeding DB from client for users with no saved server prefs. */
  const languagePrefsSeededForUserId = ref<string | null>(null)
  let languagePrefsSeedInFlight = false
  /**
   * In-session 学段 for AI generate (mirrors user.educationStage when logged in).
   * Guests can still pick a value that applies until login/logout.
   */
  const sessionEducationStage = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const isAuthSessionVerified = computed(() => hasVerifiedAuthThisSession.value)
  const userRole = computed((): UserRole | null =>
    user.value?.role ? normalizeUserRole(user.value.role) : null
  )
  const isSuperAdmin = computed(() => {
    if (userRole.value === 'superadmin') {
      return true
    }
    const payloadRole = adminCapabilitiesPayload.value?.role
    if (payloadRole && normalizeUserRole(payloadRole) === 'superadmin') {
      return true
    }
    const caps = adminCapabilitiesPayload.value?.capabilities
    return caps != null && hasSuperadminPanelAccess(caps)
  })
  const isPlatformBd = computed(() => userRole.value === 'platform_bd')
  const isExpert = computed(() => userRole.value === 'expert')
  const isSchoolAdmin = computed(() => userRole.value === 'school_admin')
  const isTeacher = computed(() => userRole.value === 'teacher')
  const isPersonalTrial = computed(() => userRole.value === 'personal_trial')
  const isPersonalPaid = computed(() => userRole.value === 'personal_paid')
  const isPlatformLevel = computed(() => isSuperAdmin.value || isPlatformBd.value || isExpert.value)
  const isB2BOrgMember = computed(() => isSchoolAdmin.value || isTeacher.value)
  const isC2CConsumer = computed(() => isPersonalTrial.value || isPersonalPaid.value)
  /** Full platform admin — alias kept for existing admin-only routes */
  const isAdmin = computed(() => isSuperAdmin.value)
  /**
   * 智绘 access: prefer loaded panel capabilities (``feature.zhihui``);
   * fall back to superadmin role before capabilities hydrate.
   */
  const canAccessZhihui = computed(() => {
    if (adminCapabilitiesLoaded.value && adminCapabilitiesPayload.value != null) {
      return capsIncludeZhihui(adminCapabilitiesPayload.value.capabilities)
    }
    return isSuperAdmin.value
  })
  /** Legacy alias for school admin */
  const isManager = computed(() => isSchoolAdmin.value)
  /** Superadmin or school admin — school dashboard and org-scoped admin routes */
  const isAdminOrManager = computed(() => isSuperAdmin.value || isSchoolAdmin.value)
  /** Management panel access: from API panel_access when loaded, else role fallback */
  const isManagementPanelUser = computed(() => {
    if (adminCapabilitiesLoaded.value && adminCapabilitiesPayload.value != null) {
      return adminCapabilitiesPayload.value.panel_access
    }
    return roleHasPanelAccess(userRole.value)
  })

  // Actions
  function initFromStorage(): void {
    // Load user data from sessionStorage (not tokens - those are in httpOnly cookies)
    const storedUser = sessionStorage.getItem(USER_KEY)
    const storedMode = sessionStorage.getItem(MODE_KEY) as AuthMode

    if (storedUser) {
      try {
        const normalized = normalizeAuthUser(JSON.parse(storedUser) as User)
        user.value = normalized
        sessionEducationStage.value = normalized.educationStage ?? null
        useAiContentLevelStore().hydrateFromProfile(normalized.aiContentLevel ?? null)
        sessionStorage.setItem(USER_KEY, JSON.stringify(normalized))
      } catch {
        user.value = null
      }
    }
    if (storedMode) mode.value = storedMode

    // Also check localStorage for migration from old storage (one-time migration)
    if (!user.value) {
      const legacyUser = localStorage.getItem(USER_KEY)
      if (legacyUser) {
        try {
          const normalized = normalizeAuthUser(JSON.parse(legacyUser) as User)
          user.value = normalized
          sessionEducationStage.value = normalized.educationStage ?? null
          useAiContentLevelStore().hydrateFromProfile(normalized.aiContentLevel ?? null)
          sessionStorage.setItem(USER_KEY, JSON.stringify(normalized))
          localStorage.removeItem(USER_KEY)
          localStorage.removeItem('access_token')
        } catch {
          user.value = null
        }
      }
    }

    if (user.value) {
      useUIStore().setLanguagePolicyAllowZh(user.value.allowsSimplifiedChinese !== false)
    } else {
      useUIStore().setLanguagePolicyAllowZh(true)
    }
  }

  function setToken(newToken: string): void {
    // Token is stored in httpOnly cookie by backend, not in JavaScript
    // This is kept for backward compatibility during transition
    token.value = newToken
    // Do NOT store in localStorage - security risk
  }

  function patchThinkingCoinsSummary(summary: { balance: number; eligible: boolean }): void {
    if (!user.value) {
      return
    }
    const current = user.value.thinkingCoins
    if (current?.balance === summary.balance && current?.eligible === summary.eligible) {
      return
    }
    user.value = {
      ...user.value,
      thinkingCoins: {
        balance: summary.balance,
        eligible: summary.eligible,
      },
    }
    sessionStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  const subscriptionExpiredNotified = ref(false)

  function maybeNotifySubscriptionExpired(target: User): void {
    if (!target.subscriptionExpired || subscriptionExpiredNotified.value) {
      return
    }
    subscriptionExpiredNotified.value = true
    notify.warning(getTranslatedMessage('auth.schoolSubscriptionExpiredDowngraded'), 6000)
  }

  function applyUserLanguageFromProfile(target: User): void {
    const uiStore = useUIStore()
    uiStore.applyUiVersionFromServerProfile(target.uiVersion ?? null)
    const hasServerUi = isUiLocale(target.uiLanguage ?? null)
    const hasSavedUiLanguage =
      typeof target.uiLanguage === 'string' && target.uiLanguage.trim().length > 0
    const hasServerPrompt = isPromptOutputLanguageCode(target.promptLanguage ?? null)
    const hasServerMatch = typeof target.matchPromptToUi === 'boolean'
    if (hasServerUi || hasServerPrompt || hasServerMatch) {
      uiStore.applyLanguageFromServerProfile(
        hasServerUi ? (target.uiLanguage ?? null) : null,
        hasServerPrompt ? (target.promptLanguage ?? null) : null,
        hasServerMatch ? { matchPromptToUi: target.matchPromptToUi } : undefined
      )
    }
    if (
      hasServerUi ||
      hasSavedUiLanguage ||
      languagePrefsSeededForUserId.value === target.id ||
      languagePrefsSeedInFlight
    ) {
      return
    }
    languagePrefsSeedInFlight = true
    void (async () => {
      try {
        const ok = await saveLanguagePreferences(uiStore.language, uiStore.promptLanguage, {
          matchPromptToUi: uiStore.matchPromptToUi,
          silent: true,
        })
        if (ok) {
          languagePrefsSeededForUserId.value = target.id
        }
      } finally {
        languagePrefsSeedInFlight = false
      }
    })()
  }

  function setUser(newUser: User | BackendUser): void {
    authVerificationBlockedByNetwork.value = false
    // Normalize backend user format to frontend format
    const normalizedUser = normalizeAuthUser(newUser)
    user.value = normalizedUser
    sessionEducationStage.value = normalizedUser.educationStage ?? null
    useAiContentLevelStore().hydrateFromProfile(normalizedUser.aiContentLevel ?? null)
    maybeNotifySubscriptionExpired(normalizedUser)
    // Store in sessionStorage (cleared on browser close, not a security risk like localStorage)
    sessionStorage.setItem(USER_KEY, JSON.stringify(normalizedUser))

    // Invalidate Dify queries to trigger refetch after login
    const queryClient = getQueryClient()
    if (queryClient) {
      queryClient.invalidateQueries({ queryKey: difyKeys.all })
      queryClient.invalidateQueries({ queryKey: ['featureFlags'] })
    }
    useFeatureFlagsStore().markStale()

    useUIStore().setLanguagePolicyAllowZh(normalizedUser.allowsSimplifiedChinese !== false)
    applyUserLanguageFromProfile(normalizedUser)
  }

  async function saveLanguagePreferences(
    ui: Language,
    prompt: PromptLanguage,
    options?: { uiVersion?: string; matchPromptToUi?: boolean; silent?: boolean }
  ): Promise<boolean> {
    try {
      const body: Record<string, string | boolean> = {
        ui_language: ui,
        prompt_language: prompt,
      }
      if (options?.uiVersion) {
        body.ui_version = options.uiVersion
      }
      if (options?.matchPromptToUi !== undefined) {
        body.match_prompt_to_ui = options.matchPromptToUi
      }
      const response = await fetch(`${API_BASE}/language-preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body),
      })
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string
        ui_language?: string | null
        prompt_language?: string | null
        ui_version?: string | null
        match_prompt_to_ui?: boolean
      }
      if (!response.ok) {
        if (!options?.silent) {
          notify.error(typeof data.detail === 'string' ? data.detail : 'Failed to save preferences')
        }
        return false
      }
      if (user.value) {
        const next: User = {
          ...user.value,
          uiLanguage: data.ui_language ?? ui,
          promptLanguage: data.prompt_language ?? prompt,
          uiVersion: data.ui_version ?? options?.uiVersion ?? user.value.uiVersion,
          matchPromptToUi:
            typeof data.match_prompt_to_ui === 'boolean'
              ? data.match_prompt_to_ui
              : (options?.matchPromptToUi ?? user.value.matchPromptToUi),
        }
        user.value = next
        sessionStorage.setItem(USER_KEY, JSON.stringify(next))
      }
      return true
    } catch {
      if (!options?.silent) {
        notify.error('Failed to save preferences')
      }
      return false
    }
  }

  /**
   * Persist AI generate 学段 preference. Pass null to clear.
   * Updates in-memory session (and user on success) immediately for generate.
   */
  async function saveDiagramPreferences(educationStage: string | null): Promise<boolean> {
    const nextStage = isEducationStage(educationStage) ? educationStage : null
    const previous = sessionEducationStage.value
    sessionEducationStage.value = nextStage
    if (!isAuthenticated.value) {
      return true
    }
    try {
      const response = await fetch(`${API_BASE}/diagram-preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ education_stage: nextStage }),
      })
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string
        education_stage?: string | null
      }
      if (!response.ok) {
        sessionEducationStage.value = previous
        notify.error(typeof data.detail === 'string' ? data.detail : 'Failed to save preferences')
        return false
      }
      const saved = isEducationStage(data.education_stage) ? data.education_stage : null
      sessionEducationStage.value = saved
      if (user.value) {
        const next: User = {
          ...user.value,
          educationStage: saved,
        }
        user.value = next
        sessionStorage.setItem(USER_KEY, JSON.stringify(next))
      }
      return true
    } catch {
      sessionEducationStage.value = previous
      notify.error('Failed to save preferences')
      return false
    }
  }

  function getEffectiveEducationStage(): string | null {
    return sessionEducationStage.value
  }

  function patchPersistedUser(partial: Partial<User>): void {
    if (!user.value) {
      return
    }
    const next: User = {
      ...user.value,
      ...partial,
    }
    user.value = next
    sessionStorage.setItem(USER_KEY, JSON.stringify(next))
  }

  function setMode(newMode: AuthMode): void {
    mode.value = newMode
    sessionStorage.setItem(MODE_KEY, newMode)
  }

  function clearAuth(): void {
    const workshopUserId = user.value?.id
    disconnectWorkshopChatWsIfAny()
    if (workshopUserId) {
      clearWorkshopChatCachesForUser(workshopUserId)
    }
    resetWorkshopChatOnAuthClear(workshopUserId)
    user.value = null
    token.value = null
    mode.value = 'standard'
    hasVerifiedAuthThisSession.value = false // Reset verification flag
    languagePrefsSeededForUserId.value = null
    languagePrefsSeedInFlight = false
    sessionEducationStage.value = null
    useAiContentLevelStore().hydrateFromLocal()
    authVerificationBlockedByNetwork.value = false
    subscriptionExpiredNotified.value = false
    adminCapabilitiesPayload.value = null
    adminCapabilitiesLoaded.value = false
    lastAdminCapabilitiesFetchTime.value = 0
    lastProfileRefreshTime.value = 0
    // Clear sessionStorage
    sessionStorage.removeItem(USER_KEY)
    sessionStorage.removeItem(MODE_KEY)
    // Also clear any legacy localStorage (migration cleanup)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(MODE_KEY)
    localStorage.removeItem('access_token')
    clearSavedLoginCredentials()
    useMindMateStore().reset()
    useShowcaseStore().reset()
    stopSessionMonitoring()
    useUIStore().setLanguagePolicyAllowZh(true)
  }

  async function login(credentials: LoginCredentials): Promise<LoginResponse> {
    loading.value = true
    try {
      const payload: Record<string, string> = {
        password: credentials.password,
        captcha: credentials.captcha ?? '',
        captcha_id: credentials.captcha_id ?? '',
      }
      if (credentials.email) {
        payload.email = credentials.email
      } else {
        payload.phone = credentials.phone ?? ''
      }
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin',
      })

      const data = await response.json()

      if (response.ok && data.user) {
        setUser(data.user)
        hasVerifiedAuthThisSession.value = true // Login is verification
        lastProfileRefreshTime.value = Date.now()
        startSessionMonitoring()
        eventBus.emit('auth:login_success', {})
        return { success: true, user: user.value ?? undefined }
      }

      return { success: false, message: data.detail || data.message || 'Login failed' }
    } catch {
      return { success: false, message: 'Network error' }
    } finally {
      loading.value = false
    }
  }

  async function loginWithBayiPasskey(passkey: string): Promise<LoginResponse> {
    loading.value = true
    try {
      const response = await fetch(`${API_BASE}/bayi/passkey`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passkey }),
        credentials: 'same-origin',
      })

      let data: Record<string, unknown> = {}
      try {
        data = (await response.json()) as Record<string, unknown>
      } catch {
        /* non-JSON body */
      }

      const userPayload = data.user as Parameters<typeof normalizeAuthUser>[0] | undefined
      if (response.ok && userPayload) {
        setUser(userPayload)
        hasVerifiedAuthThisSession.value = true
        lastProfileRefreshTime.value = Date.now()
        startSessionMonitoring()
        eventBus.emit('auth:login_success', {})
        return { success: true, user: user.value ?? undefined }
      }

      const detail = data.detail as string | undefined
      const message = data.message as string | undefined
      return {
        success: false,
        message: detail || message || 'Login failed',
      }
    } catch {
      return { success: false, message: 'Network error' }
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    // Call logout endpoint - token is in httpOnly cookie
    try {
      await fetch(`${API_BASE}/logout`, {
        method: 'POST',
        credentials: 'same-origin',
      })
    } catch (error) {
      console.error('Logout error:', error)
    }

    // Clear Vue Query cache to prevent data leakage between users
    const queryClient = getQueryClient()
    if (queryClient) {
      queryClient.clear()
    }

    clearAuth()

    window.location.href = '/'
  }

  let loadAdminCapabilitiesPromise: Promise<void> | null = null

  async function fetchAdminCapabilitiesResponse(): Promise<Response> {
    return fetch('/api/auth/admin/capabilities', {
      credentials: 'same-origin',
    })
  }

  async function loadAdminCapabilities(options?: { force?: boolean }): Promise<void> {
    // sessionStorage can restore a panel role before cookies are valid. Fetching
    // here races checkAuth's /me → refresh and paints a console 401; wait until
    // the session has been verified (or recovered) in this tab.
    if (!user.value) {
      adminCapabilitiesPayload.value = null
      adminCapabilitiesLoaded.value = true
      lastAdminCapabilitiesFetchTime.value = 0
      return
    }
    if (!hasVerifiedAuthThisSession.value) {
      return
    }

    const force = options?.force === true
    const now = Date.now()
    if (
      !force &&
      adminCapabilitiesLoaded.value &&
      adminCapabilitiesPayload.value != null &&
      now - lastAdminCapabilitiesFetchTime.value < ADMIN_CAPABILITIES_CACHE_MS
    ) {
      return
    }

    if (loadAdminCapabilitiesPromise) {
      await loadAdminCapabilitiesPromise
      if (
        !force ||
        (adminCapabilitiesPayload.value != null &&
          Date.now() - lastAdminCapabilitiesFetchTime.value < ADMIN_CAPABILITIES_CACHE_MS)
      ) {
        return
      }
    }
    if (loadAdminCapabilitiesPromise) {
      return loadAdminCapabilitiesPromise
    }

    loadAdminCapabilitiesPromise = (async () => {
      try {
        const epochAtStart = getSessionRefreshEpoch()
        let response = await fetchAdminCapabilitiesResponse()
        if (response.status === 401) {
          const refreshed = await ensureFreshSessionAfterAuthFailure(epochAtStart)
          if (refreshed) {
            response = await fetchAdminCapabilitiesResponse()
          }
        }
        if (!response.ok) {
          adminCapabilitiesPayload.value = null
          return
        }
        const payload = (await response.json()) as AdminCapabilitiesPayload
        adminCapabilitiesPayload.value = payload
        lastAdminCapabilitiesFetchTime.value = Date.now()
        const apiRole = payload.role
        if (apiRole && user.value) {
          const normalizedRole = normalizeUserRole(apiRole)
          if (user.value.role !== normalizedRole) {
            user.value = { ...user.value, role: normalizedRole }
            sessionStorage.setItem(USER_KEY, JSON.stringify(user.value))
          }
        }
      } catch {
        adminCapabilitiesPayload.value = null
      } finally {
        adminCapabilitiesLoaded.value = true
      }
    })()

    try {
      await loadAdminCapabilitiesPromise
    } finally {
      loadAdminCapabilitiesPromise = null
    }
  }

  async function checkAuth(forceRefresh: boolean = false): Promise<boolean> {
    if (isMindgraphHeadlessExportSession()) {
      return false
    }

    // If user is already loaded AND we've verified auth this session, return cached state
    // This prevents redundant API calls while ensuring we verify token validity at least once
    if (!forceRefresh && user.value && hasVerifiedAuthThisSession.value) {
      authVerificationBlockedByNetwork.value = false
      // User is already loaded and verified, just ensure monitoring is started
      if (!sessionMonitorInterval.value) {
        startSessionMonitoring()
      }
      if (!adminCapabilitiesLoaded.value) {
        void loadAdminCapabilities()
      }
      return true
    }

    // If user exists but not verified yet, we need to verify (token might be expired)
    // This handles the case where sessionStorage has stale user data but token is invalid

    // Prevent duplicate concurrent calls
    if (isCheckingAuth.value) {
      // Wait for the current check to complete
      while (isCheckingAuth.value) {
        await new Promise((resolve) => setTimeout(resolve, 50))
      }
      // Return cached result (user is set if auth succeeded)
      return !!user.value
    }

    isCheckingAuth.value = true
    try {
      // Token is in httpOnly cookie, so we just make the API call
      // The cookie will be sent automatically
      const epochAtStart = getSessionRefreshEpoch()
      const response = await fetch(`${API_BASE}/me`, {
        credentials: 'same-origin',
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user || data.id) {
          setUser(data.user || data)
          hasVerifiedAuthThisSession.value = true // Mark as verified
          lastProfileRefreshTime.value = Date.now()
          void loadAdminCapabilities()
          // Only start monitoring if not already started
          if (!sessionMonitorInterval.value) {
            startSessionMonitoring()
          }
          return true
        }
      }

      // If 401, try to refresh the access token silently (refresh cookie may still be valid)
      if (response.status === 401) {
        const recovered = await tryRecoverSessionFromRefresh(epochAtStart)
        if (recovered) {
          return true
        }
      }

      // Auth failed - clear any stale user data
      if (user.value) {
        clearAuth()
      }
      return false
    } catch {
      if (user.value) {
        authVerificationBlockedByNetwork.value = true
        return true
      }
      return false
    } finally {
      isCheckingAuth.value = false
    }
  }

  /**
   * Attempt to refresh the access token using the refresh token cookie
   * Returns: { success: boolean, errorMessage?: string }
   */
  async function refreshAccessToken(): Promise<{ success: boolean; errorMessage?: string }> {
    if (isMindgraphHeadlessExportSession()) {
      return { success: false, errorMessage: 'Headless export session' }
    }
    try {
      const ok = await refreshSessionAccessToken()
      if (!ok) {
        return { success: false, errorMessage: 'Token refresh failed' }
      }
      return { success: true }
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[Auth] refreshAccessToken exception:', error)
      }
      return { success: false, errorMessage: 'Network error during token refresh' }
    }
  }

  async function detectMode(): Promise<AuthMode> {
    try {
      const response = await fetch(`${API_BASE}/mode`)
      const data = (await response.json()) as {
        mode?: string
        registration_enabled?: boolean
      }
      const detectedMode = (data.mode || 'standard') as AuthMode
      registrationEnabled.value =
        typeof data.registration_enabled === 'boolean' ? data.registration_enabled : true
      setMode(detectedMode)
      return detectedMode
    } catch {
      return 'standard'
    }
  }

  /**
   * Refresh access token via httpOnly cookie, then load /me. Used when access JWT
   * expired but the refresh session is still valid (common after idle tab time).
   *
   * Pass ``epochAtFailure`` from before the failing request so a peer refresh
   * (or recent grace window) does not rotate cookies again.
   */
  async function tryRecoverSessionFromRefresh(epochAtFailure?: number): Promise<boolean> {
    const epoch = epochAtFailure ?? getSessionRefreshEpoch()
    const refreshed = await ensureFreshSessionAfterAuthFailure(epoch)
    if (!refreshed) {
      return false
    }
    try {
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        credentials: 'same-origin',
      })
      if (!response.ok) {
        return false
      }
      const data = await response.json()
      if (!(data.user || data.id)) {
        return false
      }
      setUser(data.user || data)
      hasVerifiedAuthThisSession.value = true
      lastProfileRefreshTime.value = Date.now()
      void loadAdminCapabilities()
      if (!sessionMonitorInterval.value) {
        startSessionMonitoring()
      }
      return true
    } catch {
      return false
    }
  }

  /**
   * Reload /me after an event (login already has a payload). Not on a timer.
   * Tab-focus callers omit bypassThrottle so PROFILE_REFRESH_MIN_MS applies.
   */
  async function refreshUserProfile(options?: { bypassThrottle?: boolean }): Promise<boolean> {
    if (isMindgraphHeadlessExportSession() || !user.value) {
      return false
    }
    const now = Date.now()
    if (!options?.bypassThrottle && now - lastProfileRefreshTime.value < PROFILE_REFRESH_MIN_MS) {
      return false
    }
    lastProfileRefreshTime.value = now
    try {
      const epochAtStart = getSessionRefreshEpoch()
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        credentials: 'same-origin',
      })
      if (response.status === 401) {
        const recovered = await tryRecoverSessionFromRefresh(epochAtStart)
        if (recovered) {
          return true
        }
        handleTokenExpired('您的登录已过期，请重新登录', undefined, { skipRecovery: true })
        return false
      }
      if (!response.ok) {
        return false
      }
      const data = await response.json()
      if (data.user || data.id) {
        setUser(data.user || data)
        lastProfileRefreshTime.value = Date.now()
        return true
      }
      return false
    } catch {
      return false
    }
  }

  async function refreshToken(): Promise<boolean> {
    // First try to refresh the access token using the refresh token
    const refreshResult = await refreshAccessToken()
    if (!refreshResult.success) {
      return false
    }

    // Then fetch fresh user data
    try {
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        credentials: 'same-origin',
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user || data.id) {
          setUser(data.user || data)
        }
        return true
      }
      return false
    } catch {
      return false
    }
  }

  async function fetchCaptcha(): Promise<CaptchaResponse | null> {
    try {
      const response = await fetch(`${API_BASE}/captcha/generate`, {
        credentials: 'same-origin',
      })

      if (response.ok) {
        const data = await response.json()
        return {
          captcha_id: data.captcha_id,
          captcha_image: data.captcha_image,
        }
      }
      return null
    } catch {
      return null
    }
  }

  function onVisibleTabSessionEvents(): void {
    if (document.visibilityState !== 'visible' || !user.value) {
      return
    }
    void checkSessionStatus()
    void refreshUserProfile()
  }

  function startSessionMonitoring(): void {
    // Prevent duplicate monitoring setup
    if (sessionMonitorInterval.value) {
      return
    }

    if (!profileVisibilityListener) {
      profileVisibilityListener = onVisibleTabSessionEvents
      document.addEventListener('visibilitychange', profileVisibilityListener)
    }

    // Kick-from-another-device only. Profile (/me) is event-driven: login,
    // checkAuth, tab focus, settings save, and explicit UI events.
    sessionMonitorInterval.value = window.setInterval(() => {
      if (document.visibilityState !== 'visible') {
        return
      }
      void checkSessionStatus()
    }, SESSION_KICK_POLL_MS)

    const now = Date.now()
    if (now - lastSessionCheckTime.value > 5000) {
      lastSessionCheckTime.value = now
      void checkSessionStatus()
    }
  }

  function stopSessionMonitoring(): void {
    if (sessionMonitorInterval.value) {
      clearInterval(sessionMonitorInterval.value)
      sessionMonitorInterval.value = null
    }
    if (profileVisibilityListener) {
      document.removeEventListener('visibilitychange', profileVisibilityListener)
      profileVisibilityListener = null
    }
  }

  async function checkSessionStatus(): Promise<void> {
    if (isMindgraphHeadlessExportSession()) {
      return
    }
    // Skip session check if no user in state
    if (!user.value) {
      return
    }

    // Update last check time
    lastSessionCheckTime.value = Date.now()

    try {
      const epochAtStart = getSessionRefreshEpoch()
      const response = await fetch(`${API_BASE}/session-status`, {
        method: 'GET',
        credentials: 'same-origin',
      })

      if (response.status === 401) {
        const refreshed = await ensureFreshSessionAfterAuthFailure(epochAtStart)
        if (!refreshed) {
          handleSessionInvalidation(getTranslatedMessage('notification.sessionInvalidated'))
        }
        return
      }

      if (response.ok) {
        const data = await response.json()
        if (data.status === 'invalidated') {
          handleSessionInvalidation(data.message)
        }
      }
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[Auth] checkSessionStatus error:', error)
      }
      // Ignore errors, will retry
    }
  }

  function handleSessionInvalidation(message?: string): void {
    stopSessionMonitoring()
    alert(message || getTranslatedMessage('notification.sessionInvalidated'))
    logout()
  }

  /**
   * Handle token expiration - clears auth state and shows login modal
   * This is called when API calls return 401 due to expired JWT token
   * @param message - Optional message to display
   * @param redirectPath - Optional path to redirect to after successful login
   * @param options.skipRecovery - When true, skip another /refresh (caller already failed recovery)
   */
  function handleTokenExpired(
    message?: string,
    redirectPath?: string,
    options?: { skipRecovery?: boolean }
  ): void {
    // Prevent multiple triggers
    if (showSessionExpiredModal.value) {
      return
    }

    void (async (): Promise<void> => {
      if (!options?.skipRecovery) {
        const recovered = await tryRecoverSessionFromRefresh()
        if (recovered || showSessionExpiredModal.value) {
          return
        }
      }
      if (showSessionExpiredModal.value) {
        return
      }

      stopSessionMonitoring()

      // Clear auth state without redirect (unlike logout)
      user.value = null
      token.value = null
      languagePrefsSeededForUserId.value = null
      languagePrefsSeedInFlight = false
      authVerificationBlockedByNetwork.value = false
      sessionStorage.removeItem(USER_KEY)
      // Clear any legacy localStorage
      localStorage.removeItem('access_token')
      localStorage.removeItem('auth_user')

      // Clear Vue Query cache
      const queryClient = getQueryClient()
      if (queryClient) {
        queryClient.clear()
      }

      let effectiveMode: typeof mode.value
      try {
        effectiveMode = await detectMode()
      } catch {
        effectiveMode = mode.value
      }
      if (effectiveMode === 'bayi') {
        const safeRedirect = redirectPath ? getSafePostAuthPath(redirectPath, '/auth') : ''
        const qp = safeRedirect ? `?redirect=${encodeURIComponent(safeRedirect)}` : ''
        window.location.assign(`/auth${qp}`)
        return
      }
      if (redirectPath) {
        setPendingRedirect(getSafePostAuthPath(redirectPath, '/auth'))
      }
      notify.warning(message || getTranslatedMessage('auth.sessionExpired'), 4000)
      showSessionExpiredModal.value = true
    })()
  }

  /**
   * Close the session expired modal
   */
  function closeSessionExpiredModal(): void {
    showSessionExpiredModal.value = false
    sessionExpiredMessage.value = ''
  }

  /**
   * Set pending redirect path (for redirect after session expired login)
   */
  function setPendingRedirect(path: string | null): void {
    pendingRedirect.value = path
  }

  /**
   * Get and clear pending redirect path
   */
  function getAndClearPendingRedirect(): string | null {
    const path = pendingRedirect.value
    pendingRedirect.value = null
    return path
  }

  function patchSchoolDisplayName(displayName: string | null, fallbackName?: string): void {
    if (!user.value) {
      return
    }
    const trimmedDisplay = (displayName || '').trim()
    const trimmedFallback = (fallbackName || '').trim()
    const label = trimmedDisplay || trimmedFallback
    if (!label) {
      return
    }
    const updated = { ...user.value, schoolName: label }
    user.value = updated
    sessionStorage.setItem(USER_KEY, JSON.stringify(updated))
  }

  async function requireAuth(redirectUrl?: string): Promise<boolean> {
    const authenticated = await checkAuth()
    if (!authenticated) {
      window.location.href = redirectUrl ? getSafePostAuthPath(redirectUrl, '/auth') : '/auth'
      return false
    }
    return true
  }

  // Initialize from storage on store creation
  initFromStorage()

  registerAiContentLevelAuthBridge({
    isAuthenticated: () => isAuthenticated.value,
    patchAiContentLevel: (level) => {
      patchPersistedUser({ aiContentLevel: level })
    },
  })

  return {
    // State
    user,
    token,
    mode,
    registrationEnabled,
    loading,
    showSessionExpiredModal,
    sessionExpiredMessage,
    pendingRedirect,
    authVerificationBlockedByNetwork,
    adminCapabilitiesPayload,
    adminCapabilitiesLoaded,

    // Getters
    isAuthenticated,
    isAuthSessionVerified,
    userRole,
    isSuperAdmin,
    isPlatformBd,
    isExpert,
    isSchoolAdmin,
    isTeacher,
    isPersonalTrial,
    isPersonalPaid,
    isPlatformLevel,
    isB2BOrgMember,
    isC2CConsumer,
    isAdmin,
    canAccessZhihui,
    isManager,
    isAdminOrManager,
    isManagementPanelUser,

    // Actions
    initFromStorage,
    setToken,
    setUser,
    setMode,
    clearAuth,
    login,
    loginWithBayiPasskey,
    logout,
    checkAuth,
    detectMode,
    refreshToken,
    refreshUserProfile,
    loadAdminCapabilities,
    patchSchoolDisplayName,
    patchThinkingCoinsSummary,
    fetchCaptcha,
    startSessionMonitoring,
    stopSessionMonitoring,
    requireAuth,
    handleTokenExpired,
    closeSessionExpiredModal,
    refreshAccessToken,
    setPendingRedirect,
    getAndClearPendingRedirect,
    saveLanguagePreferences,
    saveDiagramPreferences,
    getEffectiveEducationStage,
    patchPersistedUser,
    sessionEducationStage,
  }
})
