/**
 * Shared learning-sheet visual state for raster export (PNG / SVG / PDF).
 */
import { nextTick } from 'vue'

import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import type { useDiagramStore } from '@/stores/diagram'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

type DiagramStore = ReturnType<typeof useDiagramStore>

async function waitForCanvasPaint(): Promise<void> {
  await nextTick()
  await waitForNextPaint()
}

export async function waitForExportCanvasPaint(): Promise<void> {
  await waitForCanvasPaint()
}

export function isLearningSheetRasterCapture(store: DiagramStore): boolean {
  return store.isLearningSheet && store.hasBlankedLearningSheetNodes()
}

export function learningSheetIncludeAnswers(options?: CanvasExportOptions): boolean {
  return options?.answerMode === 'include'
}

/** Run capture with answers revealed, answers hidden, or unchanged (non–learning-sheet). */
export async function runLearningSheetRasterCapture<T>(
  store: DiagramStore,
  options: CanvasExportOptions | undefined,
  capture: () => T | Promise<T>
): Promise<T> {
  if (!isLearningSheetRasterCapture(store)) {
    await waitForCanvasPaint()
    return capture()
  }

  if (learningSheetIncludeAnswers(options)) {
    return store.runWithLearningSheetAnswersRevealed(async () => {
      await waitForCanvasPaint()
      return capture()
    })
  }

  const savedShowAnswers = store.learningSheetShowAnswers
  store.setLearningSheetShowAnswers(false)
  await waitForCanvasPaint()
  try {
    return await capture()
  } finally {
    store.setLearningSheetShowAnswers(savedShowAnswers)
  }
}
