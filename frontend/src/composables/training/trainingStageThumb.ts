import { nextTick } from 'vue'

import type { TrainingCourseStep } from '@/types/training'

const STAGE_SELECTOR = '.builder-stage'
const PIXEL_RATIO = 0.55
export const CAPTURE_TIMEOUT_MS = 1200

export function raceCapture<T>(work: Promise<T>, ms: number): Promise<T | null> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), ms)
    work.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      () => {
        clearTimeout(timer)
        resolve(null)
      }
    )
  })
}

export function trainingStepPageKey(step: TrainingCourseStep | null | undefined): string {
  if (!step) return ''
  return [
    step.type,
    step.page_key || '',
    step.diagram_type || '',
    step.mindmap_canvas_mode || '',
    step.modal_key || '',
    step.focus_key || '',
    step.asset_url || '',
  ].join('|')
}

export function trainingStepThumbKey(step: TrainingCourseStep | null | undefined): string {
  if (!step) return ''
  return `${trainingStepPageKey(step)}|${JSON.stringify(step.overlays || [])}`
}

function keepCaptureNode(node: Node): boolean {
  if (!(node instanceof Element)) return true
  if (node.classList.contains('slide-preview__index')) return false
  return !node.classList.contains('step-marks')
}

export async function captureTrainingStage(): Promise<string | null> {
  const host = document.querySelector(STAGE_SELECTOR)
  if (!(host instanceof HTMLElement) || host.clientWidth < 8 || host.clientHeight < 8) {
    return null
  }
  return raceCapture(
    (async () => {
      await nextTick()
      const { toPng } = await import('html-to-image')
      return toPng(host, {
        backgroundColor: '#ffffff',
        pixelRatio: PIXEL_RATIO,
        cacheBust: true,
        filter: keepCaptureNode,
      })
    })(),
    CAPTURE_TIMEOUT_MS
  )
}
