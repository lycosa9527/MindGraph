/**
 * Concept map focus question — shared API calls for validation + suggestion SSE
 * (used by ConceptMapFocusQuestionModal and conceptMapFocusReview store)
 */
import { i18n } from '@/i18n'
import { authFetch } from '@/utils/api'

export const FOCUS_MODELS = ['qwen', 'deepseek', 'doubao'] as const
export type FocusModel = (typeof FOCUS_MODELS)[number]

export type FocusValidationState = {
  valid: boolean | null
  reason: string
  error: string | null
  loading: boolean
}

export function parseSseDataLine(line: string): Record<string, unknown> | null {
  const trimmed = line.trim()
  if (!trimmed.startsWith('data: ')) return null
  try {
    return JSON.parse(trimmed.slice(6)) as Record<string, unknown>
  } catch {
    return null
  }
}

export async function validateFocusQuestionParallel(
  question: string,
  lang: string,
  signal: AbortSignal
): Promise<Record<FocusModel, FocusValidationState>> {
  const empty = (): FocusValidationState => ({
    valid: null,
    reason: '',
    error: null,
    loading: false,
  })
  const t = (key: string) => String(i18n.global.t(key))

  const out: Record<FocusModel, FocusValidationState> = {
    qwen: { ...empty(), loading: true },
    deepseek: { ...empty(), loading: true },
    doubao: { ...empty(), loading: true },
  }

  const response = await authFetch('/api/concept_map/focus_question_review/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language: lang }),
    signal,
  })
  if (!response.ok) {
    const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
    const msg =
      typeof errBody.detail === 'string'
        ? errBody.detail
        : t('conceptMap.focus.validationRequestFailed')
    for (const m of FOCUS_MODELS) {
      out[m] = { valid: false, reason: '', error: msg, loading: false }
    }
    return out
  }
  const data = (await response.json()) as {
    results?: Array<{
      model: string
      valid: boolean
      reason: string
      error: string | null
    }>
  }
  const list = data.results ?? []
  for (const m of FOCUS_MODELS) {
    const row = list.find((r) => r.model === m)
    if (row && !row.error) {
      out[m] = {
        valid: Boolean(row.valid),
        reason: (row.reason ?? '').trim(),
        error: null,
        loading: false,
      }
    } else if (row?.error) {
      out[m] = { valid: false, reason: '', error: row.error, loading: false }
    } else {
      out[m] = { valid: false, reason: '', error: t('conceptMap.focus.noResult'), loading: false }
    }
  }
  return out
}

export async function streamFocusSuggestions(
  question: string,
  lang: string,
  avoid: string[],
  signal: AbortSignal,
  onModelSuggestions: (model: FocusModel, suggestions: string[]) => void,
  onWarning: (msg: string) => void,
  onError: (msg: string) => void
): Promise<void> {
  const response = await authFetch('/api/concept_map/focus_question_review/suggestions/stream', {
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
    onError(typeof errBody.detail === 'string' ? errBody.detail : 'Suggestions request failed')
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
