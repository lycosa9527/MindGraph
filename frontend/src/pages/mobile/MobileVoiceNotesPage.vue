<script setup lang="ts">
/**
 * Mobile Voice Notes — hub module with the same Home + Menu header as MindMate.
 * Mic stays idle until the user taps Start.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Home, Menu } from '@lucide/vue'

import MobileVoiceNotesHistory from '@/components/voiceNotes/MobileVoiceNotesHistory.vue'
import MobileVoiceNotesSheet from '@/components/voiceNotes/MobileVoiceNotesSheet.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useMobileVoiceNotesSession } from '@/composables/voiceNotes/useMobileVoiceNotesSession'
import { useVoiceNotesSessionChrome } from '@/composables/voiceNotes/useVoiceNotesSessionChrome'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { SavedDiagram } from '@/stores/savedDiagrams'

const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()
const savedDiagramsStore = useSavedDiagramsStore()
const session = useMobileVoiceNotesSession()
const { statusLabel, saveKind, statusClickable, onStatusClick } = useVoiceNotesSessionChrome({
  generating: session.generating,
  persisting: session.persisting,
})

const showSaveStatus = computed(
  () => saveKind.value === 'saved' || saveKind.value === 'unsaved' || saveKind.value === 'saving'
)

const showHistoryDrawer = ref(false)

const isLeavingLocked = computed(() => session.generating.value || session.persisting.value)

const elapsedLabel = computed(() => {
  const totalSec = Math.floor(session.voiceNotes.elapsedMs / 1000)
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

const currentHistoryDiagramId = computed(() => session.voiceNotes.diagramId)

onMounted(() => {
  void session.enterPage()
})

onBeforeUnmount(() => {
  void session.leavePage()
})

function toggleHistory(): void {
  if (isLeavingLocked.value) return
  showHistoryDrawer.value = !showHistoryDrawer.value
}

async function goHome(): Promise<void> {
  if (isLeavingLocked.value) return
  await session.leavePage()
  await router.push('/m')
}

async function openHistoryConversation(diagram: SavedDiagram): Promise<void> {
  if (isLeavingLocked.value) return
  savedDiagramsStore.setCurrentDiagram(diagram.id)
  const opened = await session.voiceNotes.openSavedConversation(diagram.id, diagram.title)
  if (!opened) return
  showHistoryDrawer.value = false
}

async function deleteHistoryDiagram(diagramId: string): Promise<boolean> {
  if (diagramId === session.voiceNotes.diagramId && session.voiceNotes.hasActiveCapture) {
    return false
  }
  const success = await savedDiagramsStore.deleteDiagram(diagramId)
  if (success) {
    notify.success(t('sidebar.diagramHistory.deleted'))
  } else {
    notify.error(t('notification.deleteFailed'))
  }
  return success
}
</script>

<template>
  <div class="mobile-voice-notes flex flex-col flex-1 min-h-0">
    <header
      class="mobile-vn-header flex items-center h-12 px-3 bg-white border-b border-gray-200 shrink-0"
    >
      <div class="flex min-w-0 flex-1 items-center gap-1">
        <button
          type="button"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg active:bg-gray-100 transition-colors"
          :aria-label="t('mobile.navHome', 'Home')"
          :disabled="isLeavingLocked"
          @click="goHome"
        >
          <Home
            :size="18"
            class="text-gray-500"
          />
        </button>
        <button
          type="button"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg active:bg-gray-100 transition-colors"
          :aria-label="t('auth.voiceNotes.historyTitle')"
          :disabled="isLeavingLocked"
          @click="toggleHistory"
        >
          <Menu
            :size="18"
            class="text-gray-500"
          />
        </button>
        <span
          v-if="showSaveStatus"
          class="mobile-vn-save min-w-0 flex-1 truncate text-left text-[10px] leading-tight text-gray-500"
          :class="{
            'mobile-vn-save--dirty': saveKind === 'unsaved',
            'mobile-vn-save--saving': saveKind === 'saving',
            'mobile-vn-save--click': statusClickable,
          }"
          @click="onStatusClick"
        >
          {{ statusLabel }}
        </span>
        <h1
          class="min-w-0 flex-1 truncate text-center text-base font-semibold text-gray-800"
          :class="{ 'sr-only': showSaveStatus }"
        >
          {{ t('auth.voiceNotes.modalTitle') }}
        </h1>
      </div>
      <span class="mobile-vn-elapsed w-12 shrink-0 text-right text-xs font-semibold text-gray-500">
        {{ elapsedLabel }}
      </span>
    </header>

    <MobileVoiceNotesHistory
      v-model:visible="showHistoryDrawer"
      :current-diagram-id="currentHistoryDiagramId"
      :remove-diagram="deleteHistoryDiagram"
      @select="openHistoryConversation"
    />

    <MobileVoiceNotesSheet :session="session" />
  </div>
</template>

<style scoped>
.mobile-vn-header {
  -webkit-user-select: none;
  user-select: none;
  z-index: 10;
  padding-top: env(safe-area-inset-top);
}

.mobile-vn-elapsed {
  font-variant-numeric: tabular-nums;
}

.mobile-vn-save--dirty {
  color: #d97706;
}

.mobile-vn-save--saving {
  color: #2563eb;
}

.mobile-vn-save--click {
  cursor: pointer;
}

.mobile-vn-header button:disabled {
  opacity: 0.4;
}
</style>
