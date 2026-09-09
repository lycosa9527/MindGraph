<script setup lang="ts">
/**
 * Dedicated Voice Notes entry (Word add-in + deep link).
 * Enables the shared mic → WS Tencent ASR V2 session and opens the transcript UI.
 */
import { onMounted } from 'vue'

import { Mic, PanelLeftOpen } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { useVoiceNotesSessionChrome } from '@/composables/voiceNotes/useVoiceNotesSessionChrome'
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

const { t } = useLanguage()
const authStore = useAuthStore()
const uiStore = useUIStore()
const voiceNotes = useVoiceNotesStore()
const { statusLabel, saveKind, statusClickable, onStatusClick } = useVoiceNotesSessionChrome()

onMounted(() => {
  if (!authStore.isAuthenticated) {
    return
  }
  void voiceNotes.enableAndShowModal()
})
</script>

<template>
  <div class="voice-notes-page flex flex-1 flex-col min-h-0 overflow-hidden bg-stone-50">
    <header class="flex h-14 shrink-0 items-center gap-2 border-b border-stone-200 bg-white px-4">
      <button
        v-if="uiStore.sidebarCollapsed"
        type="button"
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-stone-100 bg-white text-stone-600 transition-colors hover:bg-stone-50"
        :title="t('sidebar.expandSidebar')"
        :aria-label="t('sidebar.expandSidebar')"
        @click="uiStore.toggleSidebar()"
      >
        <PanelLeftOpen class="h-[18px] w-[18px]" />
      </button>
      <div class="flex min-w-0 items-center gap-2">
        <Mic class="h-4 w-4 shrink-0 text-stone-700" />
        <h1 class="truncate text-sm font-semibold text-stone-800">
          {{ t('auth.voiceNotes.modalTitle') }}
        </h1>
        <button
          v-if="saveKind === 'saved' || saveKind === 'unsaved' || saveKind === 'saving'"
          type="button"
          class="truncate text-xs font-medium text-stone-500"
          :class="{
            'text-amber-600': saveKind === 'unsaved',
            'text-blue-600': saveKind === 'saving',
            'cursor-pointer': statusClickable,
            'cursor-default': !statusClickable,
          }"
          :disabled="!statusClickable"
          @click="onStatusClick"
        >
          {{ statusLabel }}
        </button>
      </div>
    </header>

    <div class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <p class="max-w-md text-sm text-stone-600">
        {{ t('auth.voiceNotes.empty') }}
      </p>
      <p
        v-if="!authStore.isAuthenticated"
        class="text-sm text-amber-700"
      >
        {{ t('auth.voiceNotes.loginRequired') }}
      </p>
      <button
        v-else
        type="button"
        class="rounded-xl bg-stone-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-stone-800"
        @click="voiceNotes.openModal()"
      >
        {{ t('auth.voiceNotes.viewTranscript') }}
      </button>
    </div>
  </div>
</template>
