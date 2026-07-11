<script setup lang="ts">
/**
 * MindGraph App Component
 * Handles dynamic layout switching based on route meta
 */
import { computed, defineAsyncComponent, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { ElConfigProvider } from 'element-plus'
import type { Language } from 'element-plus/es/locale'

import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import { useKittyDesktopActionPoll, useLanguage, useNotifications } from '@/composables'
import { useOAuthRouteFeedback } from '@/composables/auth/useOAuthRouteFeedback'
import { eventBus } from '@/composables/core/useEventBus'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { loadElementPlusLocale } from '@/i18n/elementPlusLocale'
import { isRtlUiLocale } from '@/i18n/locales'
import { useAuthStore, useFeatureFlagsStore, useUIStore } from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'
import { isGuestAuthPath, getSafePostAuthPath } from '@/utils/authRedirect'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import {
  privacyPageDocumentTitle,
  privacyPageHtmlLang,
} from '@/utils/privacyPageLocale'
import { privacyPageUiCode } from '@/composables/usePrivacyPageLocale'
import { shouldShowTestServerBannerOnVisit } from '@/utils/testServerBanner'

const notify = useNotifications()

useKittyDesktopActionPoll()

const LoginModal = defineAsyncComponent(() => import('@/components/auth/LoginModal.vue'))
const CanvasLiveSubtitleOverlay = defineAsyncComponent(
  () => import('@/components/canvas/CanvasLiveSubtitleOverlay.vue')
)
const ChatMessageToast = defineAsyncComponent(
  () => import('@/components/common/ChatMessageToast.vue')
)
const GeoLiteNotification = defineAsyncComponent(
  () => import('@/components/common/GeoLiteNotification.vue')
)
const VersionNotification = defineAsyncComponent(
  () => import('@/components/common/VersionNotification.vue')
)
const BrowserLocaleHintDialog = defineAsyncComponent(
  () => import('@/components/settings/BrowserLocaleHintDialog.vue')
)
const SwissWarningModal = defineAsyncComponent(
  () => import('@/components/common/SwissWarningModal.vue')
)
const TestServerWatermark = defineAsyncComponent(
  () => import('@/components/common/TestServerWatermark.vue')
)

const route = useRoute()
const router = useRouter()
const uiStore = useUIStore()
const authStore = useAuthStore()
const { on: onAdminEvent } = useAdminEventBus('App')
const { t } = useLanguage()

onAdminEvent('admin:mutation_completed', ({ domain, entityId }) => {
  if (domain !== 'organizations' || entityId == null || !authStore.user?.schoolId) {
    return
  }
  if (authStore.user.schoolId === String(entityId)) {
    void authStore.refreshUserProfile({ bypassThrottle: true })
  }
})
const liveTranslationStore = useLiveTranslationStore()
const {
  enabled: translationEnabled,
  connecting: translationConnecting,
  committedLines: translationCommittedLines,
  interimText: translationInterimText,
} = storeToRefs(liveTranslationStore)
/**
 * Build a stable-ID window of the last 2 committed lines.
 * The ID equals the item's global index in committedLines, so Vue's
 * TransitionGroup can track each sentence across renders without
 * re-entering elements that are still visible.
 */
const MAX_VISIBLE_COMMITTED = 2
const translationDisplayLines = computed(() => {
  const all = translationCommittedLines.value
  const start = Math.max(0, all.length - MAX_VISIBLE_COMMITTED)
  return all.slice(start).map((text, i) => ({ id: start + i, text }))
})
const translationLive = translationInterimText

const elLocale = shallowRef<Language | undefined>(undefined)

const showBrowserLocaleHint = ref(false)
/** Visibility for SwissWarningModal (@/components/common/SwissWarningModal.vue). */
const showSwissWarning = ref(false)
const showTestServerWatermark = ref(false)
/** Login succeeded before feature flags finished loading. */
const pendingLoginBanner = ref(false)
const testServerFlagsReady = ref(false)

function openSwissWarningModal(): void {
  showSwissWarning.value = true
}

function onAuthLoginSuccess(): void {
  if (!testServerFlagsReady.value) {
    pendingLoginBanner.value = true
    return
  }
  if (showTestServerWatermark.value) {
    openSwissWarningModal()
  }
}

eventBus.on('auth:login_success', onAuthLoginSuccess)
useOAuthRouteFeedback()

watch(
  () => route.path,
  (path) => {
    if (!showTestServerWatermark.value || !isGuestAuthPath(path)) {
      return
    }
    openSwissWarningModal()
  }
)

async function syncElementPlusLocale(): Promise<void> {
  elLocale.value = await loadElementPlusLocale(uiStore.language)
}

watch(
  () => uiStore.language,
  () => {
    void syncElementPlusLocale()
  },
  { immediate: true }
)

watch(
  () => route.meta.layout,
  (layout) => {
    if (layout === 'mobile' && showBrowserLocaleHint.value) {
      showBrowserLocaleHint.value = false
    }
  }
)

watch(
  () => uiStore.promptLanguage,
  async (code) => {
    await ensureFontsForLanguageCode(code)
  },
  { immediate: true }
)

const layouts = {
  default: defineAsyncComponent(() => import('@/layouts/DefaultLayout.vue')),
  editor: defineAsyncComponent(() => import('@/layouts/EditorLayout.vue')),
  auth: defineAsyncComponent(() => import('@/layouts/AuthLayout.vue')),
  main: defineAsyncComponent(() => import('@/layouts/MainLayout.vue')),
  canvas: defineAsyncComponent(() => import('@/layouts/CanvasLayout.vue')),
  mobile: defineAsyncComponent(() => import('@/layouts/MobileLayout.vue')),
}

const currentLayout = computed(() => {
  const layoutName = (route.meta.layout as keyof typeof layouts) || 'default'
  return layouts[layoutName] || layouts.default
})

watch(
  () => uiStore.isDark,
  (isDark) => {
    document.documentElement.classList.toggle('dark', isDark)
  },
  { immediate: true }
)

watch(
  () => [route.meta.titleKey, uiStore.language, route.name, privacyPageUiCode.value] as const,
  () => {
    if (route.name === 'Privacy') {
      document.title = privacyPageDocumentTitle(privacyPageUiCode.value)
      document.documentElement.lang = privacyPageHtmlLang(privacyPageUiCode.value)
      document.documentElement.dir = 'ltr'
      return
    }
    const raw = route.meta.titleKey
    const key = typeof raw === 'string' && raw.length > 0 ? raw : 'meta.pageTitle.default'
    const page = t(key)
    const brand = t('app.brandName')
    document.title = page === key ? brand : `${page} · ${brand}`
    document.documentElement.dir = isRtlUiLocale(uiStore.language) ? 'rtl' : 'ltr'
  },
  { immediate: true }
)

function handleSessionExpiredLoginSuccess() {
  document.body.style.overflow = ''

  authStore.closeSessionExpiredModal()

  const rawRedirect = authStore.getAndClearPendingRedirect()

  if (rawRedirect) {
    const redirectPath = getSafePostAuthPath(rawRedirect, '/mindmate')
    router.push(redirectPath).catch(() => {
      router.replace(redirectPath).catch(() => {
        window.location.href = redirectPath
      })
    })
  } else {
    const currentPath = router.currentRoute.value.fullPath
    router.replace(currentPath).catch(() => {
      window.location.reload()
    })
  }
}

onMounted(async () => {
  const isExportRender = route.path === '/export-render' || isMindgraphHeadlessExportSession()

  if (isExportRender) {
    testServerFlagsReady.value = true
    return
  }

  await authStore.checkAuth().catch(() => false)

  const featureFlagsStore = useFeatureFlagsStore()
  try {
    await featureFlagsStore.fetchFlags()
    if (featureFlagsStore.getFeatureTestServerBanner()) {
      showTestServerWatermark.value = true
      if (
        pendingLoginBanner.value ||
        shouldShowTestServerBannerOnVisit(route.path)
      ) {
        openSwissWarningModal()
      }
    }
  } catch {
    // Banner is best-effort; do not block app boot if flags fail.
  } finally {
    testServerFlagsReady.value = true
    pendingLoginBanner.value = false
  }

  const onGuestAuthPage = isGuestAuthPath(route.path)

  if (!onGuestAuthPage) {
    setTimeout(() => {
      notify.info(t('app.aiDisclaimer'))
    }, 500)
  }

  setTimeout(() => {
    if (
      uiStore.browserLocaleHintDismissed ||
      uiStore.uiLanguageExplicit ||
      uiStore.language !== 'zh'
    ) {
      return
    }
    const current = router.currentRoute.value
    if (onGuestAuthPage || isGuestAuthPath(current.path)) {
      return
    }
    if (current.meta.layout === 'mobile' || current.path.startsWith('/m')) {
      return
    }
    const nav = typeof navigator !== 'undefined' ? navigator.language.toLowerCase() : ''
    if (nav.startsWith('en') || nav.startsWith('az') || nav.startsWith('th')) {
      showBrowserLocaleHint.value = true
    }
  }, 800)
})

onUnmounted(() => {
  eventBus.off('auth:login_success', onAuthLoginSuccess)
})
</script>

<template>
  <ElConfigProvider :locale="elLocale">
    <component :is="currentLayout">
      <router-view v-slot="{ Component }">
        <transition
          name="fade"
          mode="out-in"
        >
          <component :is="Component" />
        </transition>
      </router-view>
    </component>

    <VersionNotification />

    <GeoLiteNotification />

    <ChatMessageToast />

    <LoginModal
      v-model:visible="authStore.showSessionExpiredModal"
      @success="handleSessionExpiredLoginSuccess"
    />

    <BrowserLocaleHintDialog v-model="showBrowserLocaleHint" />

    <!-- SwissWarningModal: reusable Swiss Design warning chrome; see component file header. -->
    <SwissWarningModal v-model="showSwissWarning" />

    <TestServerWatermark v-if="showTestServerWatermark" />

    <CanvasLiveSubtitleOverlay
      :visible="translationEnabled || translationConnecting"
      :lines="translationDisplayLines"
      :live="translationLive"
    />
  </ElConfigProvider>
</template>

<style>
/* Global styles */
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family:
    'Inter',
    system-ui,
    -apple-system,
    sans-serif;
}

#app {
  height: 100%;
}

/* Page transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Dark mode support */
.dark {
  color-scheme: dark;
}
</style>
