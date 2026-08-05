import { type Ref, ref } from 'vue'

import {
  useDiagramExport,
  useDiagramSpecForSave,
  useLanguage,
} from '@/composables'
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import { ANIMATION } from '@/config/uiConfig'
import { useUIStore } from '@/stores'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { runWithExportVisualMode } from '@/utils/canvasExportVisualMode'
import { captureDiagramPngData } from '@/utils/diagramExportRasterCapture'
import { runLearningSheetRasterCapture } from '@/utils/diagramExportLearningSheet'
import {
  prepareDiagramCanvasForRasterCapture,
  waitForDiagramExportFonts,
} from '@/utils/diagramExportPrep'
import {
  getDiagramCanvasPdfHtmlToImageOptions,
  waitForNextPaint,
} from '@/utils/diagramHtmlToImage'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'

type CanvasViewport = { x: number; y: number; zoom: number }

export interface UseDiagramCanvasExportOptions {
  vueFlowWrapper: Ref<HTMLElement | null>
  diagramStore: ReturnType<typeof useDiagramSession>
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

  /** Fit → rasterize diagram for worksheet modal preview → restore viewport. */
  async function captureWorksheetPreviewPng(
    exportOptions?: CanvasExportOptions
  ): Promise<string | null> {
    const container = vueFlowWrapper.value
    if (!container) return null

    const saved = getViewport?.() ?? null
    try {
      await prepareDiagramCanvasForRasterCapture(fitForExport)
      await waitForDiagramExportFonts(uiStore.promptLanguage)
      await waitForNextPaint()
      let dataUrl: string | null = null
      await runWithExportVisualMode(uiStore, container, exportOptions, async () => {
        const capture = await runLearningSheetRasterCapture(
          diagramStore,
          exportOptions,
          () =>
            captureDiagramPngData(
              container,
              getDiagramCanvasPdfHtmlToImageOptions({ pixelRatio: 1 })
            )
        )
        dataUrl = capture.dataUrl
      })
      return dataUrl
    } finally {
      if (saved && setViewport) {
        setViewport(saved, { duration: ANIMATION.DURATION_FAST })
      }
    }
  }

  return {
    showExportToCommunityModal,
    getExportContainer,
    getExportTitle,
    getExportSpec,
    exportByFormat,
    prepareForCommunityExport,
    restoreViewportAfterCommunityExport,
    captureWorksheetPreviewPng,
  }
}
