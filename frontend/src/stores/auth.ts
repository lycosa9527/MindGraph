/**
 * Auth Store - Pinia store for authentication state
 * Migrated from auth-helper.js
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { AuthMode, CaptchaResponse, LoginCredentials, LoginResponse, User } from '@/types'

const TOKEN_KEY = 'auth_token'
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

  function setUser(newUser: User): void {
    user.value = newUser
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
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
        setUser(data.user)
        if (data.token) setToken(data.token)
        startSessionMonitoring()
        return { success: true, user: data.user, token: data.token }
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

    try {
      await fetch(`${API_BASE}/logout`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
      })
    } catch (error) {
      console.error('Logout error:', error)
    }

    clearAuth()

    // Redirect based on mode
    if (currentMode === 'demo') {
      window.location.href = '/demo'
    } else if (currentMode === 'bayi') {
      window.location.href = '/'
    } else {
      window.location.href = '/auth'
    }
  }

  async function checkAuth(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/me`, {
        credentials: 'same-origin',
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
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
    try {
      const response = await fetch(`${API_BASE}/me`, {
        method: 'GET',
        credentials: 'same-origin',
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
      })

      if (response.ok) {
        const data = await response.json()
        if (data.user) setUser(data.user)
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
    }, 45000)

    checkSessionStatus()
  }

  function stopSessionMonitoring(): void {
    if (sessionMonitorInterval.value) {
      clearInterval(sessionMonitorInterval.value)
      sessionMonitorInterval.value = null
    }
  }

  async function checkSessionStatus(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE}/session-status`, {
        method: 'GET',
        credentials: 'same-origin',
        headers: token.value ? { Authorization: `Bearer ${token.value}` } : {},
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

    // Getters
    isAuthenticated,
    isAdmin,
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
