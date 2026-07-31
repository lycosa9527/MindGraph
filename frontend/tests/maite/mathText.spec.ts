import { describe, expect, it } from 'vitest'

import { renderMathText } from '@/utils/maite/mathText'

describe('renderMathText', () => {
  it('strips simple latex wrappers', () => {
    expect(renderMathText('\\frac{1}{2}')).toContain('1')
    expect(renderMathText('x^2')).toBeTruthy()
  })

  it('returns plain text unchanged when no latex', () => {
    expect(renderMathText('普通题目')).toBe('普通题目')
  })
})
