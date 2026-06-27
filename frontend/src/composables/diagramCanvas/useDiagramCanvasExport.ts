import { type Ref, ref } from 'vue'

import {
  useDiagramExport,
  useDiagramSpecForSave,
  useLanguage,
} from '@/composables'
import { ANIMATION } from '@/config/uiConfig'
import { useDiagramStore, useUIStore } from '@/stores'
import {
  prepareDiagramCanvasForRasterCapture,
  waitForDiagramExportFonts,
} from '@/utils/diagramExportPrep'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

type CanvasViewport = { x: number; y: number; zoom: number }

export interface UseDiagramCanvasExportOptions {
  vueFlowWrapper: Ref<HTMLElement | null>
  diagramStore: ReturnType<typeof useDiagramStore>
  fitForExport?: () => void
  getViewport?: () => CanvasViewport
  setViewport?: (viewport: CanvasViewport, opts?: { duration?: number }) => void
}

export function useDiagramCanvasExport(options: UseDiagramCanvasExportOptions) {
  const { vueFlowWrapper, diagramStore, fitForExport, getViewport, setViewport } = options

  const { currentLanguage } = useLanguage()
  const uiStore = useUIStore()

  const showExportToCommunityModal = ref(false)
  const communityViewportSnapshot = ref<CanvasViewport | null>(null)

  function getExportContainer(): HTMLElement | null {
    return vueFlowWrapper.value
  }

  function getExportTitle(): string {
    return resolveDiagramTitleForSave(
      diagramStore.effectiveTitle,
      diagramStore.type,
      currentLanguage.value
    )
  }

  const getExportSpec = useDiagramSpecForSave()

  const { exportByFormat } = useDiagramExport({
    getContainer: () => vueFlowWrapper.value,
    getDiagramSpec: getExportSpec,
    getTitle: getExportTitle,
  })

  function snapshotViewportForCommunityIfNeeded(): void {
    if (getViewport && !communityViewportSnapshot.value) {
      communityViewportSnapshot.value = getViewport()
    }
  }

  async function prepareForCommunityExport(): Promise<void> {
    snapshotViewportForCommunityIfNeeded()
    await prepareDiagramCanvasForRasterCapture(fitForExport)
    await waitForDiagramExportFonts(uiStore.promptLanguage)
  }

  function restoreViewportAfterCommunityExport(): void {
    const saved = communityViewportSnapshot.value
    if (saved && setViewport) {
      setViewport(saved, { duration: ANIMATION.DURATION_FAST })
    }
    communityViewportSnapshot.value = null
  }

  return {
    showExportToCommunityModal,
    getExportContainer,
    getExportTitle,
    getExportSpec,
    exportByFormat,
    prepareForCommunityExport,
    restoreViewportAfterCommunityExport,
  }
}
