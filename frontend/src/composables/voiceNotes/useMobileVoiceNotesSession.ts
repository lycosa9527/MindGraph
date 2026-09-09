/**
 * Mobile Voice Notes page session: idle until Start, then
 * record → stop (ingest markdown) → Generate mindmap → canvas.
 */
import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useVoiceNotesGenerate } from '@/composables/voiceNotes/useVoiceNotesGenerate'
import { useAuthStore } from '@/stores'

export function useMobileVoiceNotesSession() {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const generate = useVoiceNotesGenerate()

  const pageOpen = ref(false)

  async function enterPage(): Promise<void> {
    if (!authStore.isAuthenticated) {
      notify.warning(t('auth.voiceNotes.loginRequired'))
      return
    }
    pageOpen.value = true
    await generate.voiceNotes.enableAndOpen()
    if (!generate.voiceNotes.enabled) {
      pageOpen.value = false
    }
  }

  async function leavePage(): Promise<void> {
    if (generate.finishing.value) return
    pageOpen.value = false
    if (generate.voiceNotes.enabled) {
      await generate.voiceNotes.exit()
    }
  }

  return {
    pageOpen,
    generating: generate.generating,
    persisting: generate.persisting,
    busy: generate.busy,
    voiceNotes: generate.voiceNotes,
    enterPage,
    leavePage,
    stopRecordingOnly: generate.stopRecordingOnly,
    generateMindmap: generate.generateMindmap,
    retryFinish: generate.retryFinish,
  }
}
