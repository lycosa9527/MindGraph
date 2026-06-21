import type { ModelLoadPhase } from '@/stores/llmResults'

/** Phases that show the traveling LLM status ring (canvas buttons + MindMate avatar). */
export function isActiveLlmPhaseRing(phase: ModelLoadPhase): boolean {
  return phase === 'sending' || phase === 'waiting' || phase === 'streaming'
}

export function isLlmGenerating(phase: ModelLoadPhase): boolean {
  return phase !== 'idle' && phase !== 'error'
}
