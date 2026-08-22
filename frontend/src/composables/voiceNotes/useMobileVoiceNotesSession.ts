/**
 * Mobile Voice Notes page session: idle until Start, then
 * record → stop (ingest markdown) → Generate mindmap → canvas.
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSpecForPersist } from '@/composables/editor/useDiagramSpecForSave'
import { useMindMapDocumentSummary } from '@/composables/mindMap/useMindMapDocumentSummary'
import {
  resolveVoiceNotesCanvasPath,
  shouldGenerateMindmapAfterVoiceStop,
} from '@/composables/voiceNotes/mobileVoiceNotesFinish'
import { useAuthStore, useSavedDiagramsStore } from '@/stores'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

export function useMobileVoiceNotesSession() {
  const router = useRouter()
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const voiceNotes = useVoiceNotesStore()
  const { generateFromPackage } = useMindMapDocumentSummary()
  const getDiagramSpecForPersist = useDiagramSpecForPersist()

  const pageOpen = ref(false)
  const generating = ref(false)
  const persisting = ref(false)
  const finishing = ref(false)

  const busy = computed(
    () => generating.value || persisting.value || voiceNotes.ingesting || voiceNotes.stopping
  )

  async function enterPage(): Promise<void> {
    if (!authStore.isAuthenticated) {
      notify.warning(t('auth.voiceNotes.loginRequired'))
      return
    }
    pageOpen.value = true
    await voiceNotes.enableAndOpen()
    if (!voiceNotes.enabled) {
      pageOpen.value = false
    }
  }

  async function leavePage(): Promise<void> {
    if (finishing.value) return
    pageOpen.value = false
    if (voiceNotes.enabled) {
      await voiceNotes.exit()
    }
  }

  async function persistGeneratedSpec(diagramId: string): Promise<boolean> {
    const spec = getDiagramSpecForPersist()
    if (!spec) {
      notify.warning(t('editor.saveFailed'))
      return false
    }
    persisting.value = true
    try {
      const saved = await savedDiagramsStore.updateDiagram(diagramId, { spec })
      if (!saved) {
        notify.warning(t('editor.saveFailed'))
      }
      return saved
    } finally {
      persisting.value = false
    }
  }

  async function finishAfterStop(): Promise<void> {
    if (finishing.value) return
    const snapshot = {
      lastStopReason: voiceNotes.lastStopReason,
      transcript: voiceNotes.transcriptText,
      packageId: voiceNotes.packageId,
      diagramId: voiceNotes.diagramId,
    }
    if (!shouldGenerateMindmapAfterVoiceStop(snapshot)) {
      return
    }

    finishing.value = true
    generating.value = true
    try {
      const diagramId = snapshot.diagramId
      if (!diagramId || snapshot.packageId == null) return
      const generated = await generateFromPackage({
        packageId: snapshot.packageId,
        diagramId,
      })
      if (!generated) return
      const saved = await persistGeneratedSpec(diagramId)
      if (!saved) return
      pageOpen.value = false
      await voiceNotes.exit()
      await router.push({
        path: resolveVoiceNotesCanvasPath(router.currentRoute.value.path),
        query: { diagramId },
      })
    } finally {
      generating.value = false
      finishing.value = false
    }
  }

  async function stopRecordingOnly(): Promise<void> {
    if (!voiceNotes.hasActiveCapture) return
    await voiceNotes.stopRecording('user')
  }

  async function generateMindmap(): Promise<void> {
    if (voiceNotes.hasActiveCapture) {
      await voiceNotes.stopRecording('user')
    }
    await voiceNotes.flushTranscriptIfEdited()
    await finishAfterStop()
  }

  return {
    pageOpen,
    generating,
    persisting,
    busy,
    voiceNotes,
    enterPage,
    leavePage,
    stopRecordingOnly,
    generateMindmap,
    retryFinish: generateMindmap,
  }
}
