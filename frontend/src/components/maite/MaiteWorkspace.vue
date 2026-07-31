<script setup lang="ts">
/**
 * MaiteWorkspace — mode nav and mode content slot.
 * Header matches MindMate / AskOnce (h-14, text-sm title).
 * Recent practice lives in the app sidebar (MaitePracticeHistory).
 */
import { computed } from 'vue'

import MaiteDemoView from '@/components/maite/demo/MaiteDemoView.vue'
import MaiteInquiryView from '@/components/maite/inquiry/MaiteInquiryView.vue'
import MaiteLearningMapView from '@/components/maite/map/MaiteLearningMapView.vue'
import MaiteModeNav from '@/components/maite/MaiteModeNav.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  useMaiteNotifications,
  useMaiteOcrUpload,
  useMaiteWorkspace,
} from '@/composables/maite'

const { t } = useLanguage()
const { mode } = useMaiteWorkspace()
// Toast bridge for maite:error (OCR / map / history / inquiry / report).
useMaiteNotifications()
// Single OCR bus owner for the whole workspace (demo + inquiry share this).
useMaiteOcrUpload()

const activeView = computed(() => {
  if (mode.value === 'inquiry') {
    return MaiteInquiryView
  }
  if (mode.value === 'map') {
    return MaiteLearningMapView
  }
  return MaiteDemoView
})
</script>

<template>
  <div class="maite-workspace flex flex-col h-full bg-gray-50">
    <header
      class="maite-workspace__header h-14 px-4 flex items-center justify-between gap-3 bg-white border-b border-gray-200 shrink-0"
    >
      <div class="flex items-center gap-3 min-w-0">
        <h1 class="text-sm font-semibold text-gray-800 shrink-0">
          {{ t('maite.title') }}
        </h1>
        <span class="text-gray-300 shrink-0">|</span>
        <span
          class="text-sm text-gray-500 truncate"
          :title="t('maite.subtitle')"
        >
          {{ t('maite.subtitle') }}
        </span>
      </div>
      <MaiteModeNav class="shrink-0" />
    </header>

    <main class="maite-workspace__content flex-1 min-h-0 overflow-y-auto px-5 py-4">
      <component :is="activeView" />
    </main>
  </div>
</template>
