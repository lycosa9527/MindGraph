/**
 * Shared learning-sheet visual state for raster export (PNG / SVG / PDF).
 */
import { nextTick } from 'vue'

import type { CanvasExportOptions } from '@/config/canvasExportOptions'
import type { DiagramSession } from '@/stores/diagram'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

type DiagramStore = Pick<
  DiagramSession,
  | 'isLearningSheet'
  | 'hasBlankedLearningSheetNodes'
  | 'learningSheetShowAnswers'
  | 'setLearningSheetShowAnswers'
  | 'runWithLearningSheetAnswersRevealed'
>

/** DOM captures draw the answer row under the diagram. Vector snapshots still fill the nodes. */
export type LearningSheetAnswerCapture = 'below' | 'in-node'

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

/** Capture whatever is on the canvas now — do not toggle learning-sheet answers. */
export async function runAsShownRasterCapture<T>(capture: () => T | Promise<T>): Promise<T> {
  await waitForCanvasPaint()
  return capture()
}

/**
 * Fit measures overlay ink already in the DOM. Show or hide the answer row
 * before that measurement, then restore the user's flag.
 * Clipboard "as shown" leaves the flag alone.
 */
export async function prepareLearningSheetAnswersForFit(
  store: DiagramStore,
  options: CanvasExportOptions | undefined,
  asShown = false
): Promise<() => void> {
  if (asShown || !isLearningSheetRasterCapture(store)) {
    return () => undefined
  }
  const show = learningSheetIncludeAnswers(options)
  const saved = store.learningSheetShowAnswers
  if (saved === show) {
    return () => undefined
  }
  store.setLearningSheetShowAnswers(show)
  try {
    await waitForCanvasPaint()
  } catch (error) {
    store.setLearningSheetShowAnswers(saved)
    throw error
  }
  return () => {
    store.setLearningSheetShowAnswers(saved)
  }
}

/** Run capture with answers revealed, answers hidden, or unchanged (non–learning-sheet). */
export async function runLearningSheetRasterCapture<T>(
  store: DiagramStore,
  options: CanvasExportOptions | undefined,
  capture: () => T | Promise<T>,
  answerCapture: LearningSheetAnswerCapture = 'below'
): Promise<T> {
  if (!isLearningSheetRasterCapture(store)) {
    await waitForCanvasPaint()
    return capture()
  }

  if (learningSheetIncludeAnswers(options)) {
    if (answerCapture === 'in-node') {
      return store.runWithLearningSheetAnswersRevealed(async () => {
        await waitForCanvasPaint()
        return capture()
      })
    }
    const savedShowAnswers = store.learningSheetShowAnswers
    store.setLearningSheetShowAnswers(true)
    await waitForCanvasPaint()
    try {
      return await capture()
    } finally {
      store.setLearningSheetShowAnswers(savedShowAnswers)
    }
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
