import { CancelledError } from '@tanstack/query-core'
import { describe, expect, it } from 'vitest'

import { isIgnorableQueryError } from '@/utils/queryErrors'

describe('isIgnorableQueryError', () => {
  it('ignores abort and TanStack cancel errors', () => {
    expect(isIgnorableQueryError(null)).toBe(false)
    expect(isIgnorableQueryError(new DOMException('Aborted', 'AbortError'))).toBe(true)
    expect(isIgnorableQueryError(new CancelledError('Cancelled'))).toBe(true)
  })

  it('treats real failures as notifiable', () => {
    expect(isIgnorableQueryError(new Error('Request failed'))).toBe(false)
  })
})
