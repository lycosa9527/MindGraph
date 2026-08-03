/**
 * High-level mind-map vector export helpers (snapshot → SVG / PDF pages / DOCX PNG).
 */
import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import type { useDiagramStore } from '@/stores/diagram'
import type { useUIStore } from '@/stores/ui'
import { effectiveMindMapCanvasMode } from '@/utils/mindMapCanvasMode'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import {
  buildMindMapVectorSnapshot,
  isMindMapVectorExportType,
  type MindMapVectorSnapshot,
} from '@/utils/diagramMindMapVectorModel'
import { rasterizeMindMapVectorSvg } from '@/utils/diagramMindMapVectorRaster'
import {
  buildMindMapVectorSvg,
  mindMapVectorSvgToDataUrl,
  type MindMapVectorSvgResult,
} from '@/utils/diagramMindMapVectorSvg'
import type { PdfPageOrientation } from '@/utils/diagramPdfExport'

type DiagramStore = ReturnType<typeof useDiagramStore>
type UiStore = ReturnType<typeof useUIStore>

export function canUseMindMapVectorExport(store: DiagramStore): boolean {
  return isMindMapVectorExportType(store.type)
}

export function snapshotMindMapVectorFromStores(
  diagramStore: DiagramStore,
  uiStore: UiStore
): MindMapVectorSnapshot | null {
  const featureFlagsStore = useFeatureFlagsStore()
  const canvasMode = effectiveMindMapCanvasMode(
    uiStore.mindMapCanvasMode,
    featureFlagsStore.getFeatureMindmapV2Canvas()
  )
  return buildMindMapVectorSnapshot({
    store: {
      type: diagramStore.type,
      data: diagramStore.data,
      mindMapNodeWidths: diagramStore.mindMapNodeWidths as Record<string, number>,
      mindMapNodeHeights: diagramStore.mindMapNodeHeights as Record<string, number>,
      nodeDimensions: diagramStore.nodeDimensions as Record<
        string,
        { width: number; height: number }
      >,
      mindMapTopicActualWidth: diagramStore.mindMapTopicActualWidth,
      getDescendantIds: (rootId: string) => diagramStore.getMindMapDescendantIds(rootId),
    },
    canvasMode,
    outlineWireframe: uiStore.exportWireframeOutline,
  })
}

export function buildMindMapVectorSvgFromStores(
  diagramStore: DiagramStore,
  uiStore: UiStore
): MindMapVectorSvgResult | null {
  const snapshot = snapshotMindMapVectorFromStores(diagramStore, uiStore)
  if (!snapshot) return null
  return buildMindMapVectorSvg(snapshot)
}

export async function exportMindMapVectorSvgDataUrl(
  diagramStore: DiagramStore,
  uiStore: UiStore
): Promise<string | null> {
  const result = buildMindMapVectorSvgFromStores(diagramStore, uiStore)
  if (!result) return null
  return mindMapVectorSvgToDataUrl(result.svg)
}

export async function exportMindMapVectorDocxPng(
  diagramStore: DiagramStore,
  uiStore: UiStore
): Promise<{ blob: Blob; width: number; height: number } | null> {
  const result = buildMindMapVectorSvgFromStores(diagramStore, uiStore)
  if (!result) return null
  return rasterizeMindMapVectorSvg(result.svg)
}

export async function exportMindMapVectorPdfDocument(options: {
  orientation: PdfPageOrientation
  vectors: MindMapVectorSvgResult[]
  headerCapture?: { dataUrl: string; width: number; height: number } | null
  exportOptions?: CanvasExportOptions
}): Promise<InstanceType<(typeof import('jspdf'))['jsPDF']>> {
  // Lazy-load PDF stack so wawoff2/jsPDF never enter the app bootstrap graph.
  const { buildA4PdfFromMindMapVectors } = await import('@/utils/diagramMindMapVectorPdf')
  const worksheetText = options.exportOptions?.worksheetText
  return buildA4PdfFromMindMapVectors(
    options.vectors.map((vector, index) => ({
      vector,
      headerCapture: index === 0 ? (options.headerCapture ?? null) : null,
      diagramOffsetX: worksheetText?.diagramOffsetX ?? 0,
      diagramOffsetY: worksheetText?.diagramOffsetY ?? 0,
      diagramScale: worksheetText?.diagramScale ?? 1,
    })),
    options.orientation
  )
}
