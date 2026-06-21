import type { ModelLoadPhase } from '@/stores/llmResults'

import { isActiveLlmPhaseRing, isLlmGenerating } from '@/utils/llmLoadPhase'

export { isActiveLlmPhaseRing, isLlmGenerating }

/** @deprecated Use isActiveLlmPhaseRing */
export const isActiveMindMateRingPhase = isActiveLlmPhaseRing

/** @deprecated Use isLlmGenerating */
export const isMindMateGenerating = isLlmGenerating

export function mindMateLoadPhaseOnSendStart(): ModelLoadPhase {
  return 'sending'
}

export function mindMateLoadPhaseOnStreamOpen(): ModelLoadPhase {
  return 'waiting'
}

export function mindMateLoadPhaseOnFirstToken(): ModelLoadPhase {
  return 'streaming'
}

export function mindMateLoadPhaseOnComplete(): ModelLoadPhase {
  return 'idle'
}

export function mindMateLoadPhaseOnError(): ModelLoadPhase {
  return 'error'
}

export function mindMateLoadPhaseOnAbort(): ModelLoadPhase {
  return 'idle'
}
