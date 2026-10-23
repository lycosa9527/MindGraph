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

/**
 * On the cloned export wrapper. html-to-image copies this element, not the
 * canvas ancestor, so the hide rules are rooted here.
 */
export const LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS = 'mg-export-sheet-answers-hidden'

/** Hide the answer row and knocked-out node text for this capture. */
function setLearningSheetExportAnswersHidden(
  root: HTMLElement | null | undefined,
  hidden: boolean
): void {
  root?.classList.toggle(LEARNING_SHEET_EXPORT_HIDE_ANSWERS_CLASS, hidden)
}

/** The answer row under the diagram is on screen right now. */
export function learningSheetAnswerRowVisible(store: DiagramStore): boolean {
  return isLearningSheetRasterCapture(store) && store.learningSheetShowAnswers
}

/** Capture whatever is on the canvas now — do not toggle learning-sheet answers. */
export async function runAsShownRasterCapture<T>(capture: () => T | Promise<T>): Promise<T> {
  await waitForCanvasPaint()
  return capture()
}

/**
 * Fit measures overlay ink already in the DOM. Show or hide the answer row
 * before that measurement, then restore the user's flag.
 * Image export passes asShown and leaves the row as it is on the canvas.
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
  answerCapture: LearningSheetAnswerCapture = 'below',
  root?: HTMLElement | null
): Promise<T> {
  if (!isLearningSheetRasterCapture(store)) {
    await waitForCanvasPaint()
    return capture()
  }

  if (learningSheetIncludeAnswers(options)) {
    setLearningSheetExportAnswersHidden(root, false)
    if (answerCapture === 'in-node') {
      return store.runWithLearningSheetAnswersRevealed(async () => {
        await waitForCanvasPaint()
        return capture()
      })
    }
    const savedShowAnswers = store.learningSheetShowAnswers
    try {
      store.setLearningSheetShowAnswers(true)
      await waitForCanvasPaint()
      return await capture()
    } finally {
      store.setLearningSheetShowAnswers(savedShowAnswers)
    }
  }

  const savedShowAnswers = store.learningSheetShowAnswers
  try {
    store.setLearningSheetShowAnswers(false)
    setLearningSheetExportAnswersHidden(root, true)
    await waitForCanvasPaint()
    return await capture()
  } finally {
    setLearningSheetExportAnswersHidden(root, false)
    store.setLearningSheetShowAnswers(savedShowAnswers)
  }
}
