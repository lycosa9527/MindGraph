import { onMounted, onUnmounted, ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'
import { parseMultiLinePasteText } from '@/utils/mindMapPasteLines'

export function useMindMapMultiLinePaste(options?: {
  /** When true, paste is handled elsewhere (e.g. outline row input). */
  isBlocked?: () => boolean
}) {
  const diagramStore = useDiagramStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  const activeEditorNodeId = ref<string | null>(null)

  function isMindMapType(): boolean {
    const dt = diagramStore.type
    return dt === 'mindmap' || dt === 'mind_map'
  }

  function handlePaste(event: ClipboardEvent): boolean {
    if (options?.isBlocked?.()) return false
    if (activeEditorNodeId.value) return false
    if (!isMindMapType()) return false
    if (diagramStore.selectedNodes.length !== 1) return false

    const raw = event.clipboardData?.getData('text/plain') ?? ''
    if (!raw.trim()) return false

    const { lines, truncated } = parseMultiLinePasteText(raw)
    if (lines.length === 0) return false

    const anchorId = diagramStore.selectedNodes[0]
    const inserted = diagramStore.insertMindMapSiblingsFromLines(anchorId, lines)
    if (inserted <= 0) return false

    event.preventDefault()
    event.stopPropagation()

    notify.success(t('canvas.mindMapPaste.inserted', { count: inserted }))
    if (truncated) {
      notify.info(t('canvas.mindMapPaste.truncated'))
    }
    return true
  }

  let unsubOpen: (() => void) | null = null
  let unsubClose: (() => void) | null = null

  onMounted(() => {
    unsubOpen = eventBus.on('node_editor:opening', ({ nodeId }) => {
      activeEditorNodeId.value = nodeId
    })
    unsubClose = eventBus.on('node_editor:closed', ({ nodeId }) => {
      if (activeEditorNodeId.value === nodeId) {
        activeEditorNodeId.value = null
      }
    })
  })

  onUnmounted(() => {
    unsubOpen?.()
    unsubClose?.()
    unsubOpen = null
    unsubClose = null
  })

  return {
    handlePaste,
    activeEditorNodeId,
  }
}
