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

import { useQueryClient } from '@tanstack/vue-query'

import { notify } from '@/composables/core/notifications'
import { difyKeys } from '@/composables/queries/difyKeys'
import { i18n } from '@/i18n'
import { isPromptOutputLanguageCode, isUiLocale } from '@/i18n/locales'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { Language, PromptLanguage } from '@/stores/ui'
import type {
  AuthMode,
  BackendUser,
  CaptchaResponse,
  LoginCredentials,
  LoginResponse,
  User,
} from '@/types'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
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
  // Lazy getter for query client - only gets it when needed and in proper Vue context
  // This prevents calling useQueryClient() outside of setup/effect scope
  function getQueryClient(): ReturnType<typeof useQueryClient> | null {
    try {
      // Only call useQueryClient when actually needed, not at store initialization
      // This ensures we're in a proper Vue context (component setup or effect)
      return useQueryClient()
    } catch {
      // Vue Query not available or not in proper context
      return null
    }
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
  const loading = ref(false)
  const sessionMonitorInterval = ref<number | null>(null)
  const showSessionExpiredModal = ref(false)
  const sessionExpiredMessage = ref('')
  const pendingRedirect = ref<string | null>(null) // Store intended route after session expired login
  const isCheckingAuth = ref(false) // Prevent duplicate concurrent checkAuth calls
  const lastSessionCheckTime = ref<number>(0) // Track last session status check to prevent rapid-fire calls
  const hasVerifiedAuthThisSession = ref(false) // Track if we've verified auth with server in this session
  /** Avoid duplicate PATCH when seeding DB from client for users with no saved server prefs. */
  const languagePrefsSeededForUserId = ref<string | null>(null)
  let languagePrefsSeedInFlight = false

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin' || user.value?.role === 'superadmin')
  const isManager = computed(() => user.value?.role === 'manager')
  const isAdminOrManager = computed(() => isAdmin.value || isManager.value)
  const isSuperAdmin = computed(() => user.value?.role === 'superadmin')

  // Actions
  function initFromStorage(): void {
    // Load user data from sessionStorage (not tokens - those are in httpOnly cookies)
    const storedUser = sessionStorage.getItem(USER_KEY)
    const storedMode = sessionStorage.getItem(MODE_KEY) as AuthMode

    if (storedUser) {
      try {
        user.value = JSON.parse(storedUser)
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
          user.value = JSON.parse(legacyUser)
          // Migrate to sessionStorage
          sessionStorage.setItem(USER_KEY, legacyUser)
          // Clean up localStorage (tokens should not be there)
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

  function normalizeUser(backendUser: BackendUser): User {
    // Backend returns: id, phone, name, organization (string or object), avatar
    // Frontend expects: id, username, phone, schoolName, avatar, etc.
    let avatar = backendUser.avatar || '🐈‍⬛'
    // Handle legacy avatar_01 format - convert to emoji
    if (avatar.startsWith('avatar_')) {
      avatar = '🐈‍⬛'
    }
    // Handle organization which can be string or object
    const org = backendUser.organization
    const orgIsObject = typeof org === 'object' && org !== null
    const orgId = orgIsObject ? org.id : undefined
    const orgName = orgIsObject ? org.name : typeof org === 'string' ? org : undefined
    const orgDisplayName = orgIsObject && org.display_name ? org.display_name : undefined
    const displayLabel = orgDisplayName || orgName || backendUser.schoolName || ''

    const allowsZh = backendUser.allows_simplified_chinese !== false
    let uiLang = backendUser.ui_language ?? null
    let promptLang = backendUser.prompt_language ?? null
    if (!allowsZh) {
      if ((uiLang || '').toLowerCase() === 'zh') {
        uiLang = 'en'
      }
      if ((promptLang || '').toLowerCase() === 'zh') {
        promptLang = 'en'
      }
    }

    const loginPasswordSet =
      backendUser.login_password_set === undefined
        ? true
        : Boolean(backendUser.login_password_set)

    return {
      id: String(backendUser.id || backendUser.user?.id || ''),
      username:
        backendUser.name || backendUser.username || backendUser.phone || backendUser.email || '',
      phone: backendUser.phone || backendUser.user?.phone || '',
      email: backendUser.email,
      role: backendUser.role || 'user',
      schoolId: orgId ? String(orgId) : backendUser.schoolId,
      schoolName: displayLabel,
      avatar,
      createdAt: backendUser.created_at || backendUser.createdAt,
      lastLogin: backendUser.last_login || backendUser.lastLogin,
      uiLanguage: uiLang,
      promptLanguage: promptLang,
      uiVersion: backendUser.ui_version ?? null,
      allowsSimplifiedChinese: allowsZh,
      loginPasswordSet,
    }
  }

  function applyUserLanguageFromProfile(target: User): void {
    const uiStore = useUIStore()
    uiStore.applyUiVersionFromServerProfile(target.uiVersion ?? null)
    const hasServerUi = isUiLocale(target.uiLanguage ?? null)
    const hasServerPrompt = isPromptOutputLanguageCode(target.promptLanguage ?? null)
    if (hasServerUi || hasServerPrompt) {
      languagePrefsSeededForUserId.value = null
      uiStore.applyLanguageFromServerProfile(
        hasServerUi ? (target.uiLanguage ?? null) : null,
        hasServerPrompt ? (target.promptLanguage ?? null) : null
      )
      return
    }
    if (languagePrefsSeededForUserId.value === target.id) {
      return
    }
    if (languagePrefsSeedInFlight) {
      return
    }
    languagePrefsSeedInFlight = true
    void (async () => {
      try {
        uiStore.syncGuestLocaleFromBrowser()
        const ok = await saveLanguagePreferences(uiStore.language, uiStore.promptLanguage)
        if (ok) {
          languagePrefsSeededForUserId.value = target.id
        }
      } finally {
        languagePrefsSeedInFlight = false
      }
    })()
  }

  function setUser(newUser: User | BackendUser): void {
    // Normalize backend user format to frontend format
    const normalizedUser = normalizeUser(newUser)
    user.value = normalizedUser
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
    uiVersion?: string
  ): Promise<boolean> {
    try {
      const payload: Record<string, string> = {
        ui_language: ui,
        prompt_language: prompt,
      }
      if (uiVersion) {
        payload.ui_version = uiVersion
      }
      const response = await fetch(`${API_BASE}/language-preferences`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      })
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string
        ui_language?: string | null
        prompt_language?: string | null
        ui_version?: string | null
      }
      if (!response.ok) {
        notify.error(typeof data.detail === 'string' ? data.detail : 'Failed to save preferences')
        return false
      }
      if (user.value) {
        const next: User = {
          ...user.value,
          uiLanguage: data.ui_language ?? ui,
          promptLanguage: data.prompt_language ?? prompt,
          uiVersion: data.ui_version ?? uiVersion ?? user.value.uiVersion,
        }
        user.value = next
        sessionStorage.setItem(USER_KEY, JSON.stringify(next))
      }
      return true
    } catch {
      notify.error('Failed to save preferences')
      return false
    }
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
    // Clear sessionStorage
    sessionStorage.removeItem(USER_KEY)
    sessionStorage.removeItem(MODE_KEY)
    // Also clear any legacy localStorage (migration cleanup)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(MODE_KEY)
    localStorage.removeItem('access_token')
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
        const normalizedUser = normalizeUser(data.user)
        setUser(normalizedUser)
        hasVerifiedAuthThisSession.value = true // Login is verification
        if (data.access_token || data.token) setToken(data.access_token || data.token)
        startSessionMonitoring()
        return { success: true, user: normalizedUser, token: data.access_token || data.token }
      }

      return { success: false, message: data.detail || data.message || 'Login failed' }
    } catch {
      return { success: false, message: 'Network error' }
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    const currentMode = mode.value

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

    // Redirect to main page after logout
    if (currentMode === 'demo') {
      window.location.href = '/demo'
    } else {
      window.location.href = '/'
    }
  }

  async function checkAuth(forceRefresh: boolean = false): Promise<boolean> {
    if (isMindgraphHeadlessExportSession()) {
      return false
    }

    // If user is already loaded AND we've verified auth this session, return cached state
    // This prevents redundant API calls while ensuring we verify token validity at least once
    if (!forceRefresh && user.value && hasVerifiedAuthThisSession.value) {
      // User is already loaded and verified, just ensure monitoring is started
      if (!sessionMonitorInterval.value) {
        startSessionMonitoring()
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
      const response = await fetch(`${API_BASE}/me`, {
        credentials: 'same-origin',
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user || data.id) {
          setUser(data.user || data)
          hasVerifiedAuthThisSession.value = true // Mark as verified
          // Only start monitoring if not already started
          if (!sessionMonitorInterval.value) {
            startSessionMonitoring()
          }
          return true
        }
      }

      // If 401, try to refresh the token silently
      if (response.status === 401) {
        const refreshed = await refreshAccessToken()
        if (refreshed) {
          // Retry the auth check
          const retryResponse = await fetch(`${API_BASE}/me`, {
            credentials: 'same-origin',
          })
          if (retryResponse.ok) {
            const data = await retryResponse.json()
            if (data.user || data.id) {
              setUser(data.user || data)
              hasVerifiedAuthThisSession.value = true // Mark as verified
              // Only start monitoring if not already started
              if (!sessionMonitorInterval.value) {
                startSessionMonitoring()
              }
              return true
            }
          }
        }
      }

      // Auth failed - clear any stale user data
      if (user.value) {
        clearAuth()
      }
      return false
    } catch {
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
      const response = await fetch(`${API_BASE}/refresh`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      if (!response.ok) {
        let errorMessage: string | undefined
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || undefined
        } catch {
          /* non-JSON error body */
        }
        return { success: false, errorMessage }
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
      const data = await response.json()
      const detectedMode = (data.mode || 'standard') as AuthMode
      setMode(detectedMode)
      return detectedMode
    } catch {
      return 'standard'
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
          const userData = data.user || data
          const normalizedUser = normalizeUser(userData)
          setUser(normalizedUser)
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

  function startSessionMonitoring(): void {
    // Prevent duplicate monitoring setup
    if (sessionMonitorInterval.value) {
      return
    }

    sessionMonitorInterval.value = window.setInterval(async () => {
      if (document.visibilityState === 'visible') {
        await checkSessionStatus()
      }
    }, 120000) // 2 minutes - balance between responsiveness and server load

    // Only check immediately if not checked recently (within last 5 seconds)
    const now = Date.now()
    if (now - lastSessionCheckTime.value > 5000) {
      checkSessionStatus()
      lastSessionCheckTime.value = now
    }
  }

  function stopSessionMonitoring(): void {
    if (sessionMonitorInterval.value) {
      clearInterval(sessionMonitorInterval.value)
      sessionMonitorInterval.value = null
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
      const response = await fetch(`${API_BASE}/session-status`, {
        method: 'GET',
        credentials: 'same-origin',
      })

      if (response.status === 401) {
        // Try to refresh the token first
        const refreshResult = await refreshAccessToken()
        if (!refreshResult.success) {
          // Use backend error message if available, otherwise use generic message
          const errorMessage =
            refreshResult.errorMessage || getTranslatedMessage('notification.sessionInvalidated')
          handleSessionInvalidation(errorMessage)
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
   */
  function handleTokenExpired(message?: string, redirectPath?: string): void {
    // Prevent multiple triggers
    if (showSessionExpiredModal.value) {
      return
    }

    stopSessionMonitoring()

    // Clear auth state without redirect (unlike logout)
    user.value = null
    token.value = null
    languagePrefsSeededForUserId.value = null
    languagePrefsSeedInFlight = false
    sessionStorage.removeItem(USER_KEY)
    // Clear any legacy localStorage
    localStorage.removeItem('access_token')
    localStorage.removeItem('auth_user')

    // Clear Vue Query cache
    const queryClient = getQueryClient()
    if (queryClient) {
      queryClient.clear()
    }

    // Store redirect path if provided
    if (redirectPath) {
      setPendingRedirect(redirectPath)
    }

    notify.warning(message || getTranslatedMessage('auth.sessionExpired'), 4000)

    // Show login modal
    showSessionExpiredModal.value = true
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

  async function requireAuth(redirectUrl?: string): Promise<boolean> {
    const authenticated = await checkAuth()
    if (!authenticated) {
      if (!redirectUrl) {
        const currentMode = await detectMode()
        if (currentMode === 'demo') {
          redirectUrl = '/demo'
        } else if (currentMode === 'bayi') {
          return false
        } else {
          redirectUrl = '/auth'
        }
      }
      if (redirectUrl) {
        window.location.href = redirectUrl
      }
      return false
    }
    return true
  }

  // Initialize from storage on store creation
  initFromStorage()

  return {
    // State
    user,
    token,
    mode,
    loading,
    showSessionExpiredModal,
    sessionExpiredMessage,
    pendingRedirect,

    // Getters
    isAuthenticated,
    isAdmin,
    isManager,
    isAdminOrManager,
    isSuperAdmin,

    // Actions
    initFromStorage,
    setToken,
    setUser,
    setMode,
    clearAuth,
    login,
    logout,
    checkAuth,
    detectMode,
    refreshToken,
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
  }
})
