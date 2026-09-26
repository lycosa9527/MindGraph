<script setup lang="ts">
/**
 * MobileLayout — Minimal mobile shell.
 * Top header with back/home button + page title.
 * Content slot fills remaining space; each page owns its own bottom bar.
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ArrowLeft, Home } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { preloadMarkdownRendererForRoute } from '@/composables/core/useMarkdown'
import { useMobileCanvasSaveStatus } from '@/composables/mobile/mobileCanvasHeaderSaveStatus'
import { navigateBackFromCanvas } from '@/utils/canvasBackNavigation'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()

watch(
  () => route.path,
  (path) => {
    preloadMarkdownRendererForRoute(path)
  },
  { immediate: true }
)

const isHome = computed(() => route.name === 'MobileHome' || route.path === '/m')

const hideHeader = computed(
  () =>
    isHome.value ||
    route.name === 'MobileMindMate' ||
    route.name === 'MobileMindGraph' ||
    route.name === 'MobileKitty' ||
    route.name === 'MobileOrgs' ||
    route.name === 'MobileVoiceNotes'
)

const showBackButton = computed(() => route.name === 'MobileCanvas')
const canvasSaveStatus = useMobileCanvasSaveStatus()

const canvasSaveStatusToneClass = computed(() => {
  const tone = canvasSaveStatus.value?.tone
  if (tone === 'saving') return 'text-blue-500'
  if (tone === 'dirty') return 'text-amber-600'
  return 'text-gray-400'
})

function goBack() {
  navigateBackFromCanvas(router, route.path)
}

const pageTitle = computed(() => {
  const name = route.name as string | undefined
  if (!name) return 'MindSpring'
  const map: Record<string, string> = {
    MobileHome: 'MindSpring',
    MobileMindMate: 'MindMate',
    MobileMindGraph: 'MindGraph',
    MobileKitty: 'Kitty',
    MobileOrgs: t('mobile.orgsTitle'),
    MobileVoiceNotes: t('auth.voiceNotes.modalTitle'),
    MobileTraining: t('training.title'),
    MobileLearningSpace: t('sidebar.learningSpace'),
    MobileCanvas: 'MindGraph',
    MobileAccount: t('sidebar.account', 'Account'),
  }
  return map[name] ?? 'MindSpring'
})

function goHome() {
  router.push('/m')
}
</script>

<template>
  <div class="mobile-layout flex flex-col h-[100dvh] w-screen overflow-hidden bg-gray-50">
    <!-- Top header (hidden on landing page and MindMate — those pages own their headers) -->
    <header
      v-if="!hideHeader"
      class="mobile-header flex items-center h-12 px-3 bg-white border-b border-gray-200 shrink-0"
    >
      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="showBackButton"
          class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
          :aria-label="t('mobile.navBack', 'Back')"
          @click="goBack"
        >
          <ArrowLeft
            :size="18"
            class="text-gray-500 mg-icon-flip-rtl"
          />
        </button>

        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
          :aria-label="t('mobile.navHome', 'Home')"
          @click="goHome"
        >
          <Home
            :size="18"
            class="text-gray-500"
          />
        </button>
      </div>

      <div class="flex min-w-0 flex-1 items-center justify-center gap-2">
        <h1 class="shrink-0 text-base font-semibold text-gray-800">
          {{ pageTitle }}
        </h1>
        <span
          v-if="showBackButton && canvasSaveStatus"
          class="mobile-header-save min-w-0 truncate text-[11px] font-medium leading-tight"
          :class="canvasSaveStatusToneClass"
        >
          {{ canvasSaveStatus.text }}
        </span>
      </div>

      <div
        class="w-8 shrink-0"
        :class="{ 'w-16!': showBackButton }"
      />
    </header>

    <!-- Page content -->
    <main class="flex-1 min-h-0 flex flex-col overflow-hidden">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.mobile-header {
  -webkit-user-select: none;
  user-select: none;
  z-index: 10;
  padding-top: env(safe-area-inset-top);
}

.mobile-header-save {
  max-width: 9.5rem;
}

.mobile-layout {
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
</style>
