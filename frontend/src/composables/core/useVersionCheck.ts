/**
 * Version Check Composable
 * Detects when a new app version is available and prompts user to refresh
 */
import { onMounted, onUnmounted, ref } from 'vue'

// Version injected at build time
const APP_VERSION = __APP_VERSION__
const CHECK_INTERVAL = 5 * 60 * 1000 // 5 minutes
const VERSION_STORAGE_KEY = 'mindgraph_app_version'

export interface VersionCheckOptions {
  /** Check interval in milliseconds (default: 5 minutes) */
  interval?: number
  /** Check on route navigation (default: true) */
  checkOnNavigation?: boolean
  /** Enable periodic polling (default: true) */
  enablePolling?: boolean
}

export function useVersionCheck(options: VersionCheckOptions = {}) {
  const { interval = CHECK_INTERVAL, enablePolling = true } = options

  const currentVersion = ref(APP_VERSION)
  const serverVersion = ref<string | null>(null)
  const needsUpdate = ref(false)
  const isChecking = ref(false)
  const lastChecked = ref<Date | null>(null)

  let intervalId: ReturnType<typeof setInterval> | null = null

  /**
   * Check server for current version
   */
  async function checkVersion(): Promise<boolean> {
    if (isChecking.value) return false

    isChecking.value = true
    try {
      // Add cache-busting query param
      const response = await fetch(`/health?_t=${Date.now()}`, {
        method: 'GET',
        cache: 'no-store',
        headers: {
          Accept: 'application/json',
        },
      })

      if (!response.ok) {
        console.debug('Version check failed:', response.status)
        return false
      }

      // Check content type before parsing
      const contentType = response.headers.get('content-type')
      if (!contentType || !contentType.includes('application/json')) {
        console.debug('Version check: non-JSON response, skipping')
        return false
      }

      const data = await response.json()
      serverVersion.value = data.version
      lastChecked.value = new Date()

      // Compare versions
      if (data.version && data.version !== currentVersion.value) {
        needsUpdate.value = true
        stopPolling()
        return true
      }

      return false
    } catch (error) {
      // Silently ignore version check errors - non-critical functionality
      console.debug('Version check error:', error)
      return false
    } finally {
      isChecking.value = false
    }
  }

  /**
   * Perform hard refresh to load new version
   */
  function forceRefresh(): void {
    // Store the new version so we don't show the notification again after refresh
    if (serverVersion.value) {
      try {
        localStorage.setItem(VERSION_STORAGE_KEY, serverVersion.value)
      } catch {
        // Ignore localStorage errors
      }
    }

    // Clear any service worker caches if present
    if ('caches' in window) {
      caches.keys().then((names) => {
        names.forEach((name) => caches.delete(name))
      })
    }

    // Hard reload - bypasses browser cache
    window.location.reload()
  }

  /**
   * Dismiss the update notification (user chose to update later)
   */
  function dismissUpdate(): void {
    needsUpdate.value = false
    // Restart polling so we can remind them later
    startPolling()
  }

  /**
   * Start periodic version checking
   */
  function startPolling(): void {
    if (!enablePolling || intervalId) return

    intervalId = setInterval(() => {
      checkVersion()
    }, interval)
  }

  /**
   * Stop periodic version checking
   */
  function stopPolling(): void {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  /**
   * Check if there was a version mismatch from a previous session
   * (handles the case where user had old cached page)
   */
  function checkStoredVersion(): void {
    try {
      const storedVersion = localStorage.getItem(VERSION_STORAGE_KEY)
      if (storedVersion && storedVersion !== currentVersion.value) {
        // Version was updated since last visit - this is fine, just update storage
        localStorage.setItem(VERSION_STORAGE_KEY, currentVersion.value)
      } else if (!storedVersion) {
        // First visit - store current version
        localStorage.setItem(VERSION_STORAGE_KEY, currentVersion.value)
      }
    } catch {
      // Ignore localStorage errors
    }
  }

  // Lifecycle
  onMounted(() => {
    checkStoredVersion()
    // Initial check after a short delay (don't block app startup)
    setTimeout(() => {
      checkVersion()
    }, 3000)
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    currentVersion,
    serverVersion,
    needsUpdate,
    isChecking,
    lastChecked,
    checkVersion,
    forceRefresh,
    dismissUpdate,
    startPolling,
    stopPolling,
  }
}
