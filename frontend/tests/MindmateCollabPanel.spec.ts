import { describe, expect, it } from 'vitest'

const CODE_SAFE_RE = /[^2-9A-HJ-KM-NP-Z]/g

function sanitizeChar(raw: string): string {
  return raw.toUpperCase().replace(CODE_SAFE_RE, '')
}

function getFormattedCode(cells: string[]): string {
  const code = cells.join('')
  return code.length === 6 ? `${code.slice(0, 3)}-${code.slice(3, 6)}` : code
}

describe('MindmateCollabPanel invite code helpers', () => {
  it('sanitizes ambiguous characters', () => {
    expect(sanitizeChar('o0i1l')).toBe('')
    expect(sanitizeChar('abc')).toBe('ABC')
  })

  it('formats complete 6-char code with dash', () => {
    expect(getFormattedCode(['A', 'B', 'C', 'D', 'E', 'F'])).toBe('ABC-DEF')
  })

  it('leaves partial code unformatted', () => {
    expect(getFormattedCode(['A', 'B', 'C'])).toBe('ABC')
  })
})
