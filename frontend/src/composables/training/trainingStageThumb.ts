import { nextTick } from 'vue'

import type { TrainingCourseStep } from '@/types/training'

const STAGE_SELECTOR = '.builder-stage'
const PIXEL_RATIO = 0.55

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
  await nextTick()
  const { toPng } = await import('html-to-image')
  try {
    return await toPng(host, {
      backgroundColor: '#ffffff',
      pixelRatio: PIXEL_RATIO,
      cacheBust: true,
      filter: keepCaptureNode,
    })
  } catch {
    return null
  }
}
