import { describe, expect, it } from 'vitest'

import {
  resolveGenerateGraphErrorMessage,
  shouldNotifyGenerateGraphError,
  shouldSilenceGenerateGraphError,
} from '@/utils/generateGraphErrors'

describe('generateGraphErrors', () => {
  it('silences thinking_coin_insufficient by error type', () => {
    expect(shouldSilenceGenerateGraphError('Insufficient balance', 'thinking_coin_insufficient')).toBe(
      true
    )
    expect(shouldNotifyGenerateGraphError('', 'thinking_coin_insufficient')).toBe(false)
  })

  it('silences cancelled and in-progress errors', () => {
    expect(shouldSilenceGenerateGraphError('Cancelled')).toBe(true)
    expect(shouldSilenceGenerateGraphError('Generation already in progress')).toBe(true)
  })

  it('maps error_type to localized message', () => {
    const t = (key: string) =>
      key === 'landing.international.errorRateLimit' ? 'Too many requests' : key
    expect(resolveGenerateGraphErrorMessage('raw', 'rate_limit', t)).toBe('Too many requests')
  })

  it('uses fallback key when error is generic', () => {
    const t = (key: string) => (key === 'diagramTemplate.generationFailed' ? 'Failed' : key)
    expect(resolveGenerateGraphErrorMessage('Generation failed', undefined, t)).toBe('Failed')
  })
})
