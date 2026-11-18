/**
 * Paint alternate model/snapshot specs, rasterize, then restore the live canvas.
 */
import { nextTick } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useSnapshotHistory } from '@/composables/editor/useSnapshotHistory'
import type {
  WorksheetComparePair,
  WorksheetCompareRaster,
  WorksheetCompareSlot,
} from '@/config/canvasWorksheetText'
import { useSavedDiagramsStore } from '@/stores'
import { useLLMResultsStore } from '@/stores/llmResults'
import type { DiagramType } from '@/types'
import { cloneDiagramSpecJson } from '@/utils/cloneDiagramSpecJson'
import { dataUrlToBlob } from '@/utils/deliverExportFile'

export type { WorksheetComparePair, WorksheetCompareRaster }

type LiveSnapshot = {
  spec: Record<string, unknown>
  diagramType: DiagramType
}

function asDiagramType(value: unknown, fallback: DiagramType | null): DiagramType | null {
  if (typeof value === 'string' && value.trim()) {
    return (value === 'mind_map' ? 'mindmap' : value) as DiagramType
  }
  return fallback
}

async function waitForPaintSettle(): Promise<void> {
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

export async function resolveWorksheetCompareSlotSpec(
  slot: WorksheetCompareSlot,
  live: LiveSnapshot
): Promise<LiveSnapshot | null> {
  if (slot.kind === 'current') {
    return live
  }

  if (slot.kind === 'model') {
    const modelId = slot.id?.trim()
    if (!modelId) return null
    const llm = useLLMResultsStore()
    const result = llm.getValidResult(modelId)
    if (!result?.spec) return null
    const diagramType = asDiagramType(result.diagramType, live.diagramType)
    if (!diagramType) return null
    return {
      spec: cloneDiagramSpecJson(result.spec as Record<string, unknown>),
      diagramType,
    }
  }

  if (slot.kind === 'snapshot') {
    const version = Number.parseInt(slot.id ?? '', 10)
    if (!Number.isFinite(version) || version < 1) return null
    const saved = useSavedDiagramsStore()
    const diagramId = saved.activeDiagramId
    if (!diagramId) return null
    const { recallSnapshot } = useSnapshotHistory()
    const recalled = await recallSnapshot(diagramId, version)
    if (!recalled.ok) return null
    const diagramType = asDiagramType(
      recalled.spec.type ?? recalled.spec.diagram_type,
      live.diagramType
    )
    if (!diagramType) return null
    return {
      spec: cloneDiagramSpecJson(recalled.spec),
      diagramType,
    }
  }

  return null
}

async function paintAndRasterize(options: {
  target: LiveSnapshot
  isCurrent: boolean
  live: LiveSnapshot
  label: string
  rasterizeLive: () => Promise<{ dataUrl: string; width: number; height: number }>
}): Promise<WorksheetCompareRaster | null> {
  const diagramStore = useDiagramSession()
  const { target, isCurrent, live, label, rasterizeLive } = options

  if (!isCurrent) {
    // skipFit: export sessions block viewBus auto-fit; rasterizeLive fits itself.
    const loaded = diagramStore.loadFromSpec(target.spec, target.diagramType, {
      emitLoaded: false,
      skipFit: true,
    })
    if (!loaded) return null
    await waitForPaintSettle()
  }

  try {
    const capture = await rasterizeLive()
    if (!capture.dataUrl) return null
    return {
      dataUrl: capture.dataUrl,
      width: capture.width,
      height: capture.height,
      label,
      blob: dataUrlToBlob(capture.dataUrl),
    }
  } finally {
    if (!isCurrent) {
      diagramStore.loadFromSpec(live.spec, live.diagramType, {
        emitLoaded: false,
        skipFit: true,
      })
      await waitForPaintSettle()
    }
  }
}

/**
 * Capture left then right compare slots. Always restores the live canvas.
 */
export async function captureWorksheetComparePair(options: {
  left: WorksheetCompareSlot
  right: WorksheetCompareSlot
  labelForSlot: (slot: WorksheetCompareSlot) => string
  rasterizeLive: () => Promise<{ dataUrl: string; width: number; height: number }>
}): Promise<WorksheetComparePair | null> {
  const diagramStore = useDiagramSession()
  const liveSpec = diagramStore.getSpecForSave()
  const liveType = diagramStore.type
  if (!liveSpec || !liveType) return null

  const live: LiveSnapshot = {
    spec: cloneDiagramSpecJson(liveSpec),
    diagramType: liveType,
  }

  const leftTarget = await resolveWorksheetCompareSlotSpec(options.left, live)
  const rightTarget = await resolveWorksheetCompareSlotSpec(options.right, live)
  if (!leftTarget || !rightTarget) return null

  try {
    const left = await paintAndRasterize({
      target: leftTarget,
      isCurrent: options.left.kind === 'current',
      live,
      label: options.labelForSlot(options.left),
      rasterizeLive: options.rasterizeLive,
    })
    if (!left) return null

    const right = await paintAndRasterize({
      target: rightTarget,
      isCurrent: options.right.kind === 'current',
      live,
      label: options.labelForSlot(options.right),
      rasterizeLive: options.rasterizeLive,
    })
    if (!right) return null

    return { left, right }
  } catch (error) {
    console.error('[worksheetCompare] capture failed:', error)
    // Best-effort restore if paintAndRasterize threw mid-flight.
    diagramStore.loadFromSpec(live.spec, live.diagramType, {
      emitLoaded: false,
      skipFit: true,
    })
    await waitForPaintSettle()
    return null
  }
}
