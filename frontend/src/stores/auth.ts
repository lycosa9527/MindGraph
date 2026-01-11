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
import { computed, h, ref } from 'vue'

import { defineStore } from 'pinia'

import { ElNotification } from 'element-plus'

import { useQueryClient } from '@tanstack/vue-query'
import { AlertTriangle } from 'lucide-vue-next'

import { difyKeys } from '@/composables/queries/difyKeys'
import { translations } from '@/composables/useLanguage'
import { useUIStore } from '@/stores/ui'
import type {
  AuthMode,
  BackendUser,
  CaptchaResponse,
  LoginCredentials,
  LoginResponse,
  User,
} from '@/types'

// User data stored in sessionStorage (not tokens - those are in httpOnly cookies)
const USER_KEY = 'auth_user'
const MODE_KEY = 'auth_mode'
const API_BASE = '/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // Get query client at setup time (has proper context)
  // This may fail if Vue Query is not yet initialized, so we handle gracefully
  let queryClient: ReturnType<typeof useQueryClient> | null = null
  try {
    queryClient = useQueryClient()
  } catch {
    // Vue Query not yet initialized, will be null
  }

  // Helper to get translated message
  function getTranslatedMessage(key: string): string {
    const uiStore = useUIStore()
    const dict = translations[uiStore.language]
    return dict[key] || key
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

    return {
      id: String(backendUser.id || backendUser.user?.id || ''),
      username: backendUser.name || backendUser.username || backendUser.phone || '',
      phone: backendUser.phone || backendUser.user?.phone || '',
      email: backendUser.email,
      role: backendUser.role || 'user',
      schoolId: orgId ? String(orgId) : backendUser.schoolId,
      schoolName: orgName || backendUser.schoolName || '',
      avatar,
      createdAt: backendUser.created_at || backendUser.createdAt,
      lastLogin: backendUser.last_login || backendUser.lastLogin,
    }
  }

  function setUser(newUser: User | BackendUser): void {
    // Normalize backend user format to frontend format
    const normalizedUser = normalizeUser(newUser)
    user.value = normalizedUser
    // Store in sessionStorage (cleared on browser close, not a security risk like localStorage)
    sessionStorage.setItem(USER_KEY, JSON.stringify(normalizedUser))

    // Invalidate Dify queries to trigger refetch after login
    if (queryClient) {
      queryClient.invalidateQueries({ queryKey: difyKeys.all })
    }
  }

  function setMode(newMode: AuthMode): void {
    mode.value = newMode
    sessionStorage.setItem(MODE_KEY, newMode)
  }

  function clearAuth(): void {
    user.value = null
    token.value = null
    mode.value = 'standard'
    // Clear sessionStorage
    sessionStorage.removeItem(USER_KEY)
    sessionStorage.removeItem(MODE_KEY)
    // Also clear any legacy localStorage (migration cleanup)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(MODE_KEY)
    localStorage.removeItem('access_token')
    stopSessionMonitoring()
  }

  async function login(credentials: LoginCredentials): Promise<LoginResponse> {
    loading.value = true
    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
        credentials: 'same-origin',
      })

      const data = await response.json()

      if (response.ok && data.user) {
        const normalizedUser = normalizeUser(data.user)
        setUser(normalizedUser)
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

  async function checkAuth(): Promise<boolean> {
    // Token is in httpOnly cookie, so we just make the API call
    // The cookie will be sent automatically
    try {
      const response = await fetch(`${API_BASE}/me`, {
        credentials: 'same-origin',
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user || data.id) {
          setUser(data.user || data)
          startSessionMonitoring()
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
              startSessionMonitoring()
              return true
            }
          }
        }
      }

      return false
    } catch {
      return false
    }
  }

  /**
   * Attempt to refresh the access token using the refresh token cookie
   */
  async function refreshAccessToken(): Promise<boolean> {
    console.log('[Auth] refreshAccessToken called')
    try {
      const response = await fetch(`${API_BASE}/refresh`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      console.log(`[Auth] /refresh response: status=${response.status}, ok=${response.ok}`)
      if (!response.ok) {
        // Try to get error details from response
        try {
          const errorData = await response.json()
          console.log(`[Auth] /refresh error detail: ${JSON.stringify(errorData)}`)
        } catch {
          console.log('[Auth] /refresh failed with no JSON body')
        }
      }
      return response.ok
    } catch (error) {
      console.error('[Auth] refreshAccessToken exception:', error)
      return false
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
    const refreshed = await refreshAccessToken()
    if (!refreshed) {
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
    stopSessionMonitoring()
    console.log('[Auth] Starting session monitoring (interval: 120s)')

    sessionMonitorInterval.value = window.setInterval(async () => {
      if (document.visibilityState === 'visible') {
        console.log('[Auth] Session monitor triggered (tab visible)')
        await checkSessionStatus()
      } else {
        console.debug('[Auth] Session monitor skipped (tab hidden)')
      }
    }, 120000) // 2 minutes - balance between responsiveness and server load

    checkSessionStatus()
  }

  function stopSessionMonitoring(): void {
    if (sessionMonitorInterval.value) {
      console.log('[Auth] Stopping session monitoring')
      clearInterval(sessionMonitorInterval.value)
      sessionMonitorInterval.value = null
    }
  }

  async function checkSessionStatus(): Promise<void> {
    // Skip session check if no user in state
    if (!user.value) {
      console.debug('[Auth] checkSessionStatus skipped (no user)')
      return
    }

    console.log(`[Auth] checkSessionStatus: user=${user.value.id}`)

    try {
      const response = await fetch(`${API_BASE}/session-status`, {
        method: 'GET',
        credentials: 'same-origin',
      })

      console.log(`[Auth] /session-status response: status=${response.status}`)

      if (response.status === 401) {
        console.log('[Auth] Got 401 from /session-status, attempting token refresh...')
        // Try to refresh the token first
        const refreshed = await refreshAccessToken()
        console.log(`[Auth] Token refresh result: ${refreshed ? 'SUCCESS' : 'FAILED'}`)
        if (!refreshed) {
          console.log('[Auth] Refresh failed, calling handleSessionInvalidation')
          handleSessionInvalidation(getTranslatedMessage('notification.sessionInvalidated'))
        }
        return
      }

      if (response.ok) {
        const data = await response.json()
        console.log(`[Auth] Session status: ${data.status}`, data.message ? `message: ${data.message}` : '')
        if (data.status === 'invalidated') {
          console.log(`[Auth] Session invalidated by backend: ${data.message}`)
          handleSessionInvalidation(data.message)
        }
      }
    } catch (error) {
      console.error('[Auth] checkSessionStatus error:', error)
      // Ignore errors, will retry
    }
  }

  function handleSessionInvalidation(message?: string): void {
    console.log(`[Auth] handleSessionInvalidation called: message="${message}"`)
    stopSessionMonitoring()
    alert(message || getTranslatedMessage('notification.sessionInvalidated'))
    logout()
  }

  /**
   * Handle token expiration - clears auth state and shows login modal
   * This is called when API calls return 401 due to expired JWT token
   */
  function handleTokenExpired(message?: string): void {
    // Prevent multiple triggers
    if (showSessionExpiredModal.value) {
      return
    }

    stopSessionMonitoring()

    // Clear auth state without redirect (unlike logout)
    user.value = null
    token.value = null
    sessionStorage.removeItem(USER_KEY)
    // Clear any legacy localStorage
    localStorage.removeItem('access_token')
    localStorage.removeItem('auth_user')

    // Clear Vue Query cache
    if (queryClient) {
      queryClient.clear()
    }

    // Show notification at top of screen
    ElNotification({
      message: message || getTranslatedMessage('auth.sessionExpired'),
      type: 'warning',
      duration: 5000,
      showClose: true,
      icon: h(AlertTriangle, { size: 20 }),
      customClass: 'dark-alert-notification',
      position: 'top-right',
      offset: 16,
    })

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
          redirectUrl = '/login'
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
  }
})
