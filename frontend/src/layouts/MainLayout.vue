<script setup lang="ts">
/**
 * MainLayout - Layout with sidebar and main content area
 * Used for MindMate/MindGraph main page
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { Lock } from 'lucide-vue-next'

import { AppSidebar } from '@/components/sidebar'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { t } = useLanguage()

const isGuest = computed(() => !authStore.isAuthenticated)
const isOnLanding = computed(() => route.path === '/mindgraph')
/** Simplified (international) gallery: no sidebar; other routes use full sidebar like Chinese mode. */
const showAppSidebar = computed(
  () => uiStore.uiVersion !== 'international' || !isOnLanding.value
)

/** CN `/mindgraph`: show content clearly for guests; other main routes keep blur + login hint overlay. */
const shouldBlurGuestMain = computed(() => {
  if (!isGuest.value) return false
  if (uiStore.uiVersion === 'chinese' && route.path === '/mindgraph') return false
  return true
})
</script>

<template>
  <div class="main-layout h-screen w-screen flex overflow-hidden">
    <AppSidebar v-if="showAppSidebar" />

    <!-- Main content (blurred for guests except CN MindGraph landing; sidebar stays clear) -->
    <main
      class="main-content relative flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out"
    >
      <div
        :class="[
          'flex flex-1 flex-col min-h-0 overflow-hidden',
          shouldBlurGuestMain ? 'blur-sm pointer-events-none select-none' : '',
        ]"
      >
        <div class="main-slot flex-1 min-h-0 flex flex-col overflow-hidden">
          <slot />
        </div>
        <!-- ICP Registration Footer - Chinese version only -->
        <div
          v-if="uiStore.uiVersion === 'chinese'"
          class="icp-footer"
        >
          京ICP备2025126228号
        </div>
      </div>

      <div
        v-if="shouldBlurGuestMain"
        class="absolute inset-0 z-10 flex items-center justify-center bg-gray-50/60 dark:bg-gray-900/60 backdrop-blur-[2px]"
      >
        <div class="text-center px-4 max-w-sm">
          <div
            class="w-10 h-10 rounded-full bg-stone-100 dark:bg-stone-800 flex items-center justify-center mx-auto mb-2"
          >
            <Lock class="w-5 h-5 text-stone-400" />
          </div>
          <p class="text-sm text-stone-500 dark:text-stone-400">
            {{ t('app.guestMainLoginPrompt') }}
          </p>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.main-slot {
  flex: 1 1 0;
}

/* Slot content (pages) must fill and shrink for internal scroll to work */
.main-slot > * {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}

/* ICP Footer - reserved space at bottom, in document flow */
.icp-footer {
  flex-shrink: 0;
  padding: 12px 8px;
  text-align: center;
  font-size: 12px;
  color: #999;
  user-select: none;
  pointer-events: none;
}
</style>
