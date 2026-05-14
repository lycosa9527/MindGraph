import { describe, expect, it } from 'vitest'

import { decodeJavaModifiedUtf8 } from '@/utils/cmapModifiedUtf8'

describe('decodeJavaModifiedUtf8', () => {
  it('decodes NUL as modified UTF-8 pair', () => {
    const decoded = decodeJavaModifiedUtf8(new Uint8Array([0xc0, 0x80]))
    expect(decoded).toBe('\u0000')
  })

  it('decodes BMP UTF-8', () => {
    const decoded = decodeJavaModifiedUtf8(new Uint8Array([0xe4, 0xb8, 0xad]))
    expect(decoded).toBe('中')
  })
})
