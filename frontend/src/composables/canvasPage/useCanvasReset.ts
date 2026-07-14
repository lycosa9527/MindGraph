import { loadElMessageBox } from '@/composables/core/notifications'
import { useRouter } from 'vue-router'

import { applyCanvasSessionReset } from '@/composables/canvasPage/applyCanvasSessionReset'
import { eventBus, getDefaultDiagramName, useLanguage, useNotifications } from '@/composables'
import { useDiagramStore } from '@/stores'
import type { DiagramType } from '@/types'

/**
 * Reset canvas to the default template for the current diagram type.
 * Shared by CanvasTopBar and mind-map toolbar.
 */
export function useCanvasReset() {
  const router = useRouter()
  const diagramStore = useDiagramStore()
  const notify = useNotifications()
  const { t, currentLanguage } = useLanguage()

  async function resetToDefaultTemplate(): Promise<void> {
    const diagramType = diagramStore.type as DiagramType | null
    if (!diagramType) {
      notify.warning(t('canvas.reset.warnSelectType'))
      return
    }

    try {
      const ElMessageBox = await loadElMessageBox()
      await ElMessageBox.confirm(t('canvas.reset.confirmBody'), t('canvas.reset.confirmTitle'), {
        confirmButtonText: t('canvas.reset.confirmButton'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
      })
    } catch {
      return
    }

    applyCanvasSessionReset()
    await router.replace({ path: '/canvas', query: { type: diagramType } })
    diagramStore.loadDefaultTemplate(diagramType)
    diagramStore.initTitle(getDefaultDiagramName(diagramType, currentLanguage.value))
    eventBus.emit('view:fit_to_canvas_requested', { animate: true, userInitiated: true })
    notify.success(t('notification.resetDefaultTemplate'))
  }

  return { resetToDefaultTemplate }
}
