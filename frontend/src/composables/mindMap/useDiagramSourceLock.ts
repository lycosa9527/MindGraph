/**
 * Ribbon lock: one Document Summary source family per diagram.
 */
import { computed, ref } from 'vue'

import { storeToRefs } from 'pinia'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { usePackageDetail } from '@/composables/fileCenter/useFileCenter'
import { useFileCenterActivePackage } from '@/composables/fileCenter/useFileCenterActivePackage'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import { useVoiceNotesStore } from '@/stores'
import {
  type DiagramSourceKind,
  diagramSourceLockMessage,
  isDiagramSourceKindLocked,
  resolveLockedSourceKind,
} from '@/utils/diagramSourceKind'

export function useDiagramSourceLock() {
  const { t } = useLanguage()
  const notify = useNotifications()
  const voiceNotes = useVoiceNotesStore()
  const { hasActiveCapture } = storeToRefs(voiceNotes)
  const fileCenterEnabled = ref(DOC_SUMMARY_LITE_UI)
  const { activePackageId } = useFileCenterActivePackage(fileCenterEnabled)
  const detailQuery = usePackageDetail(activePackageId, {
    enabled: fileCenterEnabled,
    apiMode: 'doc_summary',
  })

  const packageLockedKind = computed(() =>
    resolveLockedSourceKind(detailQuery.data.value?.documents ?? [])
  )

  const lockedKind = computed<DiagramSourceKind | null>(() => {
    if (hasActiveCapture.value) {
      return 'voice'
    }
    return packageLockedKind.value
  })

  const lockMessage = computed(() => {
    const kind = lockedKind.value
    if (!kind) return ''
    return diagramSourceLockMessage((key, named) => t(key, named ?? {}), kind)
  })

  function isLocked(requested: DiagramSourceKind): boolean {
    return isDiagramSourceKindLocked(lockedKind.value, requested)
  }

  function notifyLocked(): void {
    const message = lockMessage.value
    if (message) {
      notify.warning(message)
    }
  }

  return {
    lockedKind,
    lockMessage,
    isLocked,
    notifyLocked,
  }
}
