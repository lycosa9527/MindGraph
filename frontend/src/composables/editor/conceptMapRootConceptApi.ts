/**
 * Concept map: root concept — single-shot generate (legacy) and multi-model suggestion SSE.
 */
import {
  FOCUS_MODELS,
  type FocusModel,
  parseSseDataLine,
} from '@/composables/editor/conceptMapFocusQuestionApi'
import { authFetch } from '@/utils/api'

export type RootConceptGenerateResult = {
  recommended_root_concept: string
  brief_reason: string
}

export async function generateRootConceptFromFocusQuestion(
  question: string,
  lang: string,
  signal?: AbortSignal
): Promise<RootConceptGenerateResult> {
  const response = await authFetch('/api/concept_map/root_concept/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language: lang }),
    signal,
  })
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
    const msg = typeof errBody.detail === 'string' ? errBody.detail : 'Root concept request failed'
    throw new Error(msg)
  }
  const data = (await response.json()) as RootConceptGenerateResult
  if (!data.recommended_root_concept?.trim()) {
    throw new Error('Empty root concept')
  }
  return data
}

export async function streamRootConceptSuggestions(
  question: string,
  lang: string,
  avoid: string[],
  signal: AbortSignal,
  onModelSuggestions: (model: FocusModel, suggestions: string[]) => void,
  onWarning: (msg: string) => void,
  onError: (msg: string) => void
): Promise<void> {
  const response = await authFetch('/api/concept_map/root_concept/suggestions/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      language: lang,
      avoid: avoid.length ? avoid : undefined,
    }),
    signal,
  })
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
    onError(typeof errBody.detail === 'string' ? errBody.detail : 'Root concept suggestions failed')
    return
  }
  const reader = response.body?.getReader()
  if (!reader) {
    onError('Could not read suggestion stream')
    return
  }
  const decoder = new TextDecoder()
  let lineBuffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      lineBuffer += decoder.decode(value, { stream: true })
      const lines = lineBuffer.split('\n')
      lineBuffer = lines.pop() ?? ''
      for (const line of lines) {
        const payload = parseSseDataLine(line.replace(/\r$/, ''))
        if (!payload) continue
        const ev = payload.event as string
        if (ev === 'model_suggestions') {
          const model = payload.model
          const sug = payload.suggestions
          if (
            typeof model === 'string' &&
            (FOCUS_MODELS as readonly string[]).includes(model) &&
            Array.isArray(sug)
          ) {
            const texts = sug.map((s) => String(s).trim()).filter(Boolean)
            if (texts.length > 0) {
              onModelSuggestions(model as FocusModel, texts)
            }
          }
        } else if (ev === 'model_error' && typeof payload.message === 'string') {
          onWarning(`${payload.model ?? '?'}: ${payload.message}`)
        } else if (ev === 'error' && typeof payload.message === 'string') {
          onError(payload.message)
        }
      }
    }
    if (lineBuffer.trim()) {
      parseSseDataLine(lineBuffer.replace(/\r$/, ''))
    }
  } finally {
    reader.releaseLock()
  }
}
