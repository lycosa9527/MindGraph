/**
 * Auth Store - Pinia store for authentication state
 * Migrated from auth-helper.js
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { AuthMode, CaptchaResponse, LoginCredentials, LoginResponse, User } from '@/types'

const TOKEN_KEY = 'access_token'
const USER_KEY = 'auth_user'
const MODE_KEY = 'auth_mode'
const API_BASE = '/api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const mode = ref<AuthMode>('standard')
  const loading = ref(false)
  const sessionMonitorInterval = ref<number | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin' || user.value?.role === 'superadmin')
  const isManager = computed(() => user.value?.role === 'manager')
  const isAdminOrManager = computed(() => isAdmin.value || isManager.value)
  const isSuperAdmin = computed(() => user.value?.role === 'superadmin')

  // Actions
  function initFromStorage(): void {
    const storedToken = localStorage.getItem(TOKEN_KEY)
    const storedUser = localStorage.getItem(USER_KEY)
    const storedMode = localStorage.getItem(MODE_KEY) as AuthMode

    if (storedToken) token.value = storedToken
    if (storedUser) {
      try {
        user.value = JSON.parse(storedUser)
      } catch {
        user.value = null
      }
    }
    if (storedMode) mode.value = storedMode
  }

  function setToken(newToken: string): void {
    token.value = newToken
    localStorage.setItem(TOKEN_KEY, newToken)
  }

  function normalizeUser(backendUser: any): User {
    // Backend returns: id, phone, name, organization (string or object), avatar
    // Frontend expects: id, username, phone, schoolName, avatar, etc.
    let avatar = backendUser.avatar || '🐈‍⬛'
    // Handle legacy avatar_01 format - convert to emoji
    if (avatar.startsWith('avatar_')) {
      avatar = '🐈‍⬛'
    }
    return {
      id: String(backendUser.id || backendUser.user?.id || ''),
      username: backendUser.name || backendUser.username || backendUser.phone || '',
      phone: backendUser.phone || backendUser.user?.phone || '',
      email: backendUser.email,
      role: backendUser.role || 'user',
      schoolId: backendUser.organization?.id
        ? String(backendUser.organization.id)
        : backendUser.schoolId,
      schoolName:
        backendUser.organization?.name || backendUser.organization || backendUser.schoolName || '',
      avatar,
      createdAt: backendUser.created_at || backendUser.createdAt,
      lastLogin: backendUser.last_login || backendUser.lastLogin,
    }
  }

  function setUser(newUser: User | any): void {
    // Normalize backend user format to frontend format
    const normalizedUser = normalizeUser(newUser)
    user.value = normalizedUser
    localStorage.setItem(USER_KEY, JSON.stringify(normalizedUser))
  }

  function setMode(newMode: AuthMode): void {
    mode.value = newMode
    localStorage.setItem(MODE_KEY, newMode)
  }

  function clearAuth(): void {
    user.value = null
    token.value = null
    mode.value = 'standard'
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(MODE_KEY)
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

      return { success: false, message: data.message || 'Login failed' }
    } catch {
      return { success: false, message: 'Network error' }
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    const currentMode = mode.value

    // Only call logout endpoint if we have a token
    if (token.value) {
      try {
        await fetch(`${API_BASE}/logout`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Authorization: `Bearer ${token.value}` },
        })
      } catch (error) {
        console.error('Logout error:', error)
      }
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
    // If no token exists, user is definitely not authenticated
    // Skip the API call to avoid unnecessary 401 errors
    if (!token.value) {
      return false
    }

    try {
      const response = await fetch(`${API_BASE}/me`, {
        credentials: 'same-origin',
        headers: { Authorization: `Bearer ${token.value}` },
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user || data.id) {
          setUser(data.user || data)
          startSessionMonitoring()
          return true
        }
      }

      return false
    } catch {
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
    // If no token exists, nothing to refresh
    if (!token.value) {
      return false
    }

    try {
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { Authorization: `Bearer ${token.value}` },
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

    sessionMonitorInterval.value = window.setInterval(async () => {
      if (document.visibilityState === 'visible') {
        await checkSessionStatus()
      }
    }, 120000) // 2 minutes - balance between responsiveness and server load

    checkSessionStatus()
  }

  function stopSessionMonitoring(): void {
    if (sessionMonitorInterval.value) {
      clearInterval(sessionMonitorInterval.value)
      sessionMonitorInterval.value = null
    }
  }

  async function checkSessionStatus(): Promise<void> {
    // Skip session check if no token exists
    if (!token.value) {
      return
    }

    try {
      const response = await fetch(`${API_BASE}/session-status`, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { Authorization: `Bearer ${token.value}` },
      })

      if (response.status === 401) {
        handleSessionInvalidation(
          'Your session was invalidated because you logged in from another location'
        )
        return
      }

      if (response.ok) {
        const data = await response.json()
        if (data.status === 'invalidated') {
          handleSessionInvalidation(data.message)
        }
      }
    } catch {
      // Ignore errors, will retry
    }
  }

  function handleSessionInvalidation(message: string): void {
    stopSessionMonitoring()
    alert(message || 'Your account was logged in from another location.')
    logout()
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
  }
})
