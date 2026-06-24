/**
 * Landing-specific helpers; core error mapping lives in generateGraphErrors.ts.
 */
import type { GenerateGraphCompletePayload } from '@/utils/generateGraphStream'
import {
  extractFailureFromPayload,
  extractSpecFailure,
  resolveGenerateGraphErrorMessage,
  shouldNotifyGenerateGraphError,
  shouldSilenceGenerateGraphError,
  type GenerateGraphFailureDetails,
} from '@/utils/generateGraphErrors'

export type LandingFailureDetails = GenerateGraphFailureDetails

export {
  extractFailureFromPayload,
  extractSpecFailure,
  shouldNotifyGenerateGraphError as shouldNotifyLandingError,
  shouldSilenceGenerateGraphError as shouldSilenceLandingError,
}

export function normalizeDiagramTypeForLabel(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) {
    return undefined
  }
  const normalized = value.trim()
  return normalized === 'mind_map' ? 'mindmap' : normalized
}

export function topicPreviewFromPrompt(prompt: unknown, maxLength = 48): string {
  if (typeof prompt !== 'string') {
    return ''
  }
  const trimmed = prompt.trim()
  if (!trimmed) {
    return ''
  }
  if (trimmed.length <= maxLength) {
    return trimmed
  }
  return `${trimmed.slice(0, maxLength)}…`
}

export function resolveDiagramTypeLabel(
  diagramType: unknown,
  t: (key: string) => string
): string {
  const normalized = normalizeDiagramTypeForLabel(diagramType)
  if (!normalized) {
    return String(t('landing.international.diagramTypePending'))
  }
  const key = `sidebar.diagramType.${normalized}`
  const label = t(key)
  return label !== key ? label : normalized
}

export function resolveLandingErrorMessage(
  rawError: string,
  errorType: string | undefined,
  t: (key: string) => string
): string {
  return resolveGenerateGraphErrorMessage(rawError, errorType, t)
}
