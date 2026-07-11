/**
 * Display helpers for one-sentence edits queued while multi-LLM auto-complete runs.
 * FIFO queue + request lifecycle live in ``useOneSentenceStore``.
 */
import type { ModelLoadPhase, ModelState } from '@/stores/llmResults'

const MODEL_DISPLAY_NAMES: Record<string, string> = {
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  doubao: 'Doubao',
}

const IN_FLIGHT_PHASES: ReadonlySet<ModelLoadPhase> = new Set([
  'sending',
  'waiting',
  'streaming',
])

export function listInFlightAutocompleteDisplayNames(
  modelStates: Record<string, ModelState>,
  modelPhases: Record<string, ModelLoadPhase>
): string[] {
  const names: string[] = []
  for (const [model, state] of Object.entries(modelStates)) {
    const phase = modelPhases[model] ?? 'idle'
    const inFlight = state === 'loading' || IN_FLIGHT_PHASES.has(phase)
    if (!inFlight) {
      continue
    }
    names.push(MODEL_DISPLAY_NAMES[model] ?? model)
  }
  return names
}

export function joinDisplayNames(names: string[], lang: 'zh' | 'en'): string {
  if (names.length === 0) {
    return ''
  }
  if (names.length === 1) {
    return names[0]
  }
  if (lang === 'zh') {
    if (names.length === 2) {
      return `${names[0]} 和 ${names[1]}`
    }
    return `${names.slice(0, -1).join('、')} 和 ${names[names.length - 1]}`
  }
  if (names.length === 2) {
    return `${names[0]} and ${names[1]}`
  }
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`
}

type KittyEditQueuedTranslate = {
  (key: 'canvas.mindMapOneSentence.kittyEditBusyQueuedGeneric'): string
  (
    key: 'canvas.mindMapOneSentence.kittyEditBusyQueued',
    params: Record<string, string> | { models: string }
  ): string
}

export function buildKittyEditQueuedForLlmMessage(
  translate: KittyEditQueuedTranslate,
  modelNames: string[],
  lang: 'zh' | 'en'
): string {
  if (modelNames.length === 0) {
    return translate('canvas.mindMapOneSentence.kittyEditBusyQueuedGeneric')
  }
  return translate('canvas.mindMapOneSentence.kittyEditBusyQueued', {
    models: joinDisplayNames(modelNames, lang),
  })
}
