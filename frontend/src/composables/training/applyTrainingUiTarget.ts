import { nextTick } from 'vue'

import {
  requestTrainingModalOpen,
  requestTrainingModalsClose,
} from '@/composables/training/trainingCommands'
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

export function queryTrainingFocus(
  focusKey: string | null | undefined,
  stageOnly = false
): HTMLElement | null {
  const selector = trainingFocusSelector(focusKey)
  if (!selector || typeof document === 'undefined') return null
  const staged = document.querySelector(
    `.builder-stage ${selector}, .teacher-preview ${selector}`
  )
  if (staged instanceof HTMLElement) return staged
  if (stageOnly) return null
  const host = document.querySelector(selector)
  return host instanceof HTMLElement ? host : null
}

async function waitForTrainingFocus(focusKey: string, stageOnly: boolean): Promise<void> {
  for (let attempt = 0; attempt < FOCUS_WAIT_FRAMES; attempt += 1) {
    if (queryTrainingFocus(focusKey, stageOnly)) return
    await waitFrame()
  }
}

export async function applyTrainingUiTarget(options: {
  modalKey?: string | null
  focusKey?: string | null
  hostModals?: boolean
}): Promise<void> {
  const training = useTrainingStore()
  const hostModals = options.hostModals !== false
  training.setUiFocus(null)
  if (hostModals) {
    if (options.modalKey) {
      requestTrainingModalOpen(options.modalKey)
    } else {
      requestTrainingModalsClose()
    }
  }
  if (!options.focusKey) return
  await nextTick()
  await waitForTrainingFocus(options.focusKey, !hostModals)
  training.setUiFocus(options.focusKey)
  const def = trainingFocusDef(options.focusKey)
  if (!def?.activateOnApply) return
  queryTrainingFocus(options.focusKey, !hostModals)?.click()
}
