import { describe, expect, it } from 'vitest'

import {
  extractFailureFromPayload,
  extractSpecFailure,
  resolveLandingErrorMessage,
  topicPreviewFromPrompt,
} from '@/composables/mindgraph/landingGenerateGraphErrors'

describe('landingGenerateGraphErrors', () => {
  it('extracts nested spec error without success flag', () => {
    const failure = extractSpecFailure({
      error: 'Failed to generate specification',
      error_type: 'generation',
    })
    expect(failure?.error).toBe('Failed to generate specification')
    expect(failure?.errorType).toBe('generation')
  })

  it('extracts failure from complete payload', () => {
    const failure = extractFailureFromPayload({
      success: false,
      spec: {
        error: 'Categories 1 must be 衣',
        error_type: 'generation',
      },
    })
    expect(failure?.error).toContain('Categories 1')
  })

  it('truncates long topic previews', () => {
    const preview = topicPreviewFromPrompt('a'.repeat(60), 48)
    expect(preview.endsWith('…')).toBe(true)
    expect(preview.length).toBe(49)
  })

  it('maps error_type to localized fallback key', () => {
    const t = (key: string) => (key === 'landing.international.errorRateLimit' ? 'Too many requests' : key)
    expect(resolveLandingErrorMessage('raw', 'rate_limit', t)).toBe('Too many requests')
  })
})
