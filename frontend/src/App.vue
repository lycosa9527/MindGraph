<script setup lang="ts">
/**
 * MindGraph App Component
 * Handles dynamic layout switching based on route meta
 */
import { computed, defineAsyncComponent, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { ElConfigProvider } from 'element-plus'
import type { Language } from 'element-plus/es/locale'
import en from 'element-plus/es/locale/lang/en'

import { LoginModal } from '@/components/auth'
import ChatMessageToast from '@/components/common/ChatMessageToast.vue'
import GeoLiteNotification from '@/components/common/GeoLiteNotification.vue'
import VersionNotification from '@/components/common/VersionNotification.vue'
import CanvasLiveSubtitleOverlay from '@/components/canvas/CanvasLiveSubtitleOverlay.vue'
import BrowserLocaleHintDialog from '@/components/settings/BrowserLocaleHintDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { loadElementPlusLocale } from '@/i18n/elementPlusLocale'
import { isRtlUiLocale } from '@/i18n/locales'
import { useAuthStore, useUIStore } from '@/stores'
import { useLiveTranslationStore } from '@/stores/liveTranslation'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const notify = useNotifications()

const route = useRoute()
const router = useRouter()
const uiStore = useUIStore()
const authStore = useAuthStore()
const { t } = useLanguage()
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

const elLocale = shallowRef<Language>(en)

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
  () => uiStore.promptLanguage,
  async (code) => {
    await ensureFontsForLanguageCode(code)
  },
  { immediate: true }
)

const showBrowserLocaleHint = ref(false)

const layouts = {
  default: defineAsyncComponent(() => import('@/layouts/DefaultLayout.vue')),
  editor: defineAsyncComponent(() => import('@/layouts/EditorLayout.vue')),
  admin: defineAsyncComponent(() => import('@/layouts/AdminLayout.vue')),
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
  () => [route.meta.titleKey, uiStore.language] as const,
  () => {
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

  const redirectPath = authStore.getAndClearPendingRedirect()

  if (redirectPath) {
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

  if (!isExportRender) {
    await authStore.checkAuth().catch(() => false)

    setTimeout(() => {
      notify.info(t('app.aiDisclaimer'))
    }, 500)

    setTimeout(() => {
      if (
        uiStore.browserLocaleHintDismissed ||
        uiStore.uiLanguageExplicit ||
        uiStore.language !== 'zh'
      ) {
        return
      }
      const nav = typeof navigator !== 'undefined' ? navigator.language.toLowerCase() : ''
      if (nav.startsWith('en') || nav.startsWith('az') || nav.startsWith('th')) {
        showBrowserLocaleHint.value = true
      }
    }, 800)
  }
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
