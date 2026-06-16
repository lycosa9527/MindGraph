import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores'
import type { SidebarQuote } from '@/types/sidebar-quotes'

import {
  type SidebarQuoteLocaleBucket,
  clearQuoteSessionCache,
  detectSidebarQuoteUserLogin,
  formatQuoteDisplayLine,
  loadSidebarQuotePool,
  pickRandomQuoteExcluding,
  preferQuotesWithAuthor,
  quoteLocaleBucket,
  quoteSessionShownAt,
  readQuoteSessionCache,
  remainingQuoteRotateMs,
  rememberSidebarQuoteUser,
  resetSidebarQuotePageSession,
  resetSidebarQuoteSessionState,
  resolveSidebarQuote,
  writeQuoteSessionForPick,
} from './sidebarQuotePicker'

let rotateTimer: ReturnType<typeof setTimeout> | null = null
let rotateCallback: (() => void) | null = null

function clearRotateTimer(): void {
  if (rotateTimer != null) {
    clearTimeout(rotateTimer)
    rotateTimer = null
  }
}

function scheduleRotateTimer(callback: () => void): void {
  clearRotateTimer()
  rotateCallback = callback
  const cache = readQuoteSessionCache()
  const delay = remainingQuoteRotateMs(quoteSessionShownAt(cache))
  rotateTimer = setTimeout(() => {
    rotateCallback?.()
  }, delay)
}

export function useSidebarPhilosophyQuote() {
  const authStore = useAuthStore()
  const { currentLanguage } = useLanguage()

  const quote = ref<SidebarQuote | null>(null)
  const loading = ref(false)
  const activeBucket = ref<SidebarQuoteLocaleBucket | null>(null)
  let loadGeneration = 0

  function requestQuoteRotation(): void {
    clearQuoteSessionCache()
    resetSidebarQuotePageSession()
    void loadQuote({ forceNew: true })
  }

  async function loadQuote(options: { forceNew: boolean }): Promise<void> {
    if (!authStore.isAuthenticated || authStore.user?.id == null) {
      quote.value = null
      clearRotateTimer()
      rotateCallback = null
      return
    }

    const bucket = quoteLocaleBucket(currentLanguage.value)
    const generation = ++loadGeneration
    loading.value = true

    try {
      const pool = await loadSidebarQuotePool(bucket)
      if (generation !== loadGeneration) {
        return
      }

      const pickPool = preferQuotesWithAuthor(pool)
      const previousId = quote.value?.id ?? null

      activeBucket.value = bucket
      const cachedId = options.forceNew ? null : (readQuoteSessionCache()?.id ?? null)
      const picked = options.forceNew
        ? pickRandomQuoteExcluding(pickPool, previousId)
        : resolveSidebarQuote(pickPool, cachedId)

      quote.value = picked
      if (picked) {
        writeQuoteSessionForPick(picked, { forceNew: options.forceNew })
        scheduleRotateTimer(requestQuoteRotation)
      } else {
        clearRotateTimer()
        rotateCallback = null
      }
    } catch {
      quote.value = null
      clearRotateTimer()
      rotateCallback = null
    } finally {
      if (generation === loadGeneration) {
        loading.value = false
      }
    }
  }

  function handleVisibilityChange(): void {
    if (typeof document === 'undefined') {
      return
    }
    if (document.visibilityState === 'hidden') {
      clearRotateTimer()
      return
    }
    if (authStore.isAuthenticated && quote.value) {
      scheduleRotateTimer(requestQuoteRotation)
    }
  }

  watch(
    () =>
      [
        authStore.isAuthenticated,
        authStore.user?.id ?? null,
        quoteLocaleBucket(currentLanguage.value),
      ] as const,
    ([authenticated, userId, bucket]) => {
      if (!authenticated || userId == null) {
        loadGeneration += 1
        quote.value = null
        activeBucket.value = null
        clearRotateTimer()
        rotateCallback = null
        clearQuoteSessionCache()
        resetSidebarQuoteSessionState()
        return
      }

      const isLogin = detectSidebarQuoteUserLogin(userId)
      const bucketChanged = activeBucket.value != null && activeBucket.value !== bucket
      const forceNew = isLogin || bucketChanged

      if (forceNew) {
        clearQuoteSessionCache()
        resetSidebarQuotePageSession()
      }

      rememberSidebarQuoteUser(userId)
      void loadQuote({ forceNew })
    },
    { immediate: true }
  )

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  const quoteLine = computed(() => formatQuoteDisplayLine(quote.value))

  return {
    quote,
    quoteLine,
    loading,
  }
}
