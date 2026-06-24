/**
 * Shared generate_graph failure parsing and user-facing error messages
 * (landing, canvas autocomplete, mind-map subgraph).
 */
import type { GenerateGraphCompletePayload } from '@/utils/generateGraphStream'

export interface GenerateGraphFailureDetails {
  error: string
  errorType?: string
  showGuidance?: boolean
}

const SILENT_ERROR_TYPES = new Set(['thinking_coin_insufficient'])

const ERROR_TYPE_I18N_KEYS: Record<string, string> = {
  rate_limit: 'landing.international.errorRateLimit',
  timeout: 'landing.international.errorTimeout',
  content_filter: 'landing.international.errorContentFilter',
  validation: 'landing.international.errorValidation',
  generation: 'landing.international.errorGeneration',
  workflow: 'landing.international.errorGeneration',
  service_error: 'landing.international.errorGeneration',
  internal: 'landing.international.errorInternal',
}

export function extractSpecFailure(spec: unknown): GenerateGraphFailureDetails | null {
  if (!spec || typeof spec !== 'object') {
    return null
  }
  const payload = spec as {
    success?: boolean
    error?: string
    error_type?: string
    show_guidance?: boolean
  }
  if (typeof payload.error !== 'string' || !payload.error.trim()) {
    return null
  }
  if (payload.success === true) {
    return null
  }
  return {
    error: payload.error.trim(),
    errorType: typeof payload.error_type === 'string' ? payload.error_type : undefined,
    showGuidance: payload.show_guidance === true,
  }
}

export function extractFailureFromPayload(
  result: GenerateGraphCompletePayload | Record<string, unknown>
): GenerateGraphFailureDetails | null {
  if (typeof result.error === 'string' && result.error.trim()) {
    return {
      error: result.error.trim(),
      errorType: typeof result.error_type === 'string' ? result.error_type : undefined,
      showGuidance: result.show_guidance === true,
    }
  }
  const specFailure = extractSpecFailure(result.spec)
  if (specFailure) {
    return specFailure
  }
  if (result.success === false) {
    return {
      error: 'Generation failed',
      errorType: typeof result.error_type === 'string' ? result.error_type : undefined,
      showGuidance: result.show_guidance === true,
    }
  }
  if (!result.success || !result.spec) {
    return { error: 'Generation failed' }
  }
  return null
}

export function resolveGenerateGraphErrorMessage(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string,
  fallbackKey = 'diagramTemplate.generationFailed'
): string {
  if (errorType && ERROR_TYPE_I18N_KEYS[errorType]) {
    const localized = t(ERROR_TYPE_I18N_KEYS[errorType])
    if (localized !== ERROR_TYPE_I18N_KEYS[errorType]) {
      return localized
    }
  }
  const genericKeys = new Set(['Generation failed', 'Unknown error', 'Request failed'])
  if (rawError && !genericKeys.has(rawError)) {
    return rawError
  }
  return String(t(fallbackKey))
}

export function shouldSilenceGenerateGraphError(error: string, errorType?: string): boolean {
  if (error === 'Cancelled' || error === 'Generation already in progress') {
    return true
  }
  return Boolean(errorType && SILENT_ERROR_TYPES.has(errorType))
}

export function shouldNotifyGenerateGraphError(error: string, errorType?: string): boolean {
  return !shouldSilenceGenerateGraphError(error, errorType)
}
