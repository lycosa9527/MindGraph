import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { eventBus, getDefaultDiagramName, useLanguage, useNotifications } from '@/composables'
import { useDiagramStore, useLLMResultsStore, usePanelsStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'

/**
 * Reset canvas to the default template for the current diagram type.
 * Shared by CanvasTopBar and mind-map toolbar.
 */
export function useCanvasReset() {
  const router = useRouter()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const panelsStore = usePanelsStore()
  const notify = useNotifications()
  const { t, currentLanguage } = useLanguage()

  async function resetToDefaultTemplate(): Promise<void> {
    const diagramType = diagramStore.type as DiagramType | null
    if (!diagramType) {
      notify.warning(t('canvas.reset.warnSelectType'))
      return
    }

    try {
      await ElMessageBox.confirm(t('canvas.reset.confirmBody'), t('canvas.reset.confirmTitle'), {
        confirmButtonText: t('canvas.reset.confirmButton'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      })
    } catch {
      return
    }

    savedDiagramsStore.clearActiveDiagram()
    router.replace({ path: '/canvas', query: { type: diagramType } })
    useLLMResultsStore().reset()
    panelsStore.reset()
    diagramStore.clearHistory()
    diagramStore.loadDefaultTemplate(diagramType)
    diagramStore.initTitle(getDefaultDiagramName(diagramType, currentLanguage.value))
    if (diagramType !== 'concept_map' && !isMindMapDiagramType(diagramType)) {
      eventBus.emit('view:fit_to_canvas_requested', { animate: true })
    }
    notify.success(t('notification.resetDefaultTemplate'))
  }

  return { resetToDefaultTemplate }
}
