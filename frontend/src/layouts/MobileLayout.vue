<script setup lang="ts">
/**
 * MobileLayout — Minimal mobile shell.
 * Top header with back/home button + page title.
 * Content slot fills remaining space; each page owns its own bottom bar.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ArrowLeft, Home } from 'lucide-vue-next'

import { useLanguage } from '@/composables'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()

const isHome = computed(() => route.name === 'MobileHome' || route.path === '/m')

const hideHeader = computed(
  () => isHome.value || route.name === 'MobileMindMate' || route.name === 'MobileMindGraph'
)

const showBackButton = computed(() => route.name === 'MobileCanvas')

function goBack() {
  router.push('/m/mindgraph')
}

const pageTitle = computed(() => {
  const name = route.name as string | undefined
  if (!name) return 'MindSpring'
  const map: Record<string, string> = {
    MobileHome: 'MindSpring',
    MobileMindMate: 'MindMate',
    MobileMindGraph: 'MindGraph',
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
          @click="goBack"
        >
          <ArrowLeft
            :size="18"
            class="text-gray-500"
          />
        </button>

        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg active:bg-gray-100 transition-colors"
          @click="goHome"
        >
          <Home
            :size="18"
            class="text-gray-500"
          />
        </button>
      </div>

      <h1 class="flex-1 text-center text-base font-semibold text-gray-800 truncate">
        {{ pageTitle }}
      </h1>

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
}
</style>
