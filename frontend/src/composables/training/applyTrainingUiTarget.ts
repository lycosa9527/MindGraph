import { nextTick } from 'vue'

import {
  closeTrainingModals,
  openTrainingModal,
} from '@/composables/training/trainingUiBridge'
import { trainingFocusDef, trainingFocusSelector } from '@/config/trainingUiTargets'
import { useTrainingStore } from '@/stores/training'

const FOCUS_WAIT_FRAMES = 16

function waitFrame(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => resolve())
      return
    }
    resolve()
  })
}

export function queryTrainingFocus(focusKey: string | null | undefined): HTMLElement | null {
  const selector = trainingFocusSelector(focusKey)
  if (!selector || typeof document === 'undefined') return null
  return (
    document.querySelector(`.builder-stage ${selector}`) || document.querySelector(selector)
  )
}

async function waitForTrainingFocus(focusKey: string): Promise<void> {
  for (let attempt = 0; attempt < FOCUS_WAIT_FRAMES; attempt += 1) {
    if (queryTrainingFocus(focusKey)) return
    await waitFrame()
  }
}

export async function applyTrainingUiTarget(options: {
  modalKey?: string | null
  focusKey?: string | null
}): Promise<void> {
  const training = useTrainingStore()
  training.setUiFocus(null)
  if (options.modalKey) {
    openTrainingModal(options.modalKey)
  } else {
    closeTrainingModals()
  }
  if (!options.focusKey) return
  await nextTick()
  await waitForTrainingFocus(options.focusKey)
  training.setUiFocus(options.focusKey)
  const def = trainingFocusDef(options.focusKey)
  if (!def?.activateOnApply) return
  queryTrainingFocus(options.focusKey)?.click()
}
