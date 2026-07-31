import { describe, expect, it } from 'vitest'

import { parseMaiteSseBlock } from '@/api/maite/client'

describe('parseMaiteSseBlock', () => {
  it('parses event and json data lines', () => {
    const block = 'event: complete\ndata: {"ok":true}\n\n'
    const parsed = parseMaiteSseBlock(block)
    expect(parsed.event).toBe('complete')
    expect(parsed.data).toEqual({ ok: true })
  })

  it('defaults event to message', () => {
    const parsed = parseMaiteSseBlock('data: {"x":1}\n\n')
    expect(parsed.event).toBe('message')
    expect(parsed.data).toEqual({ x: 1 })
  })
})
