import { describe, expect, it } from 'vitest'

import { collectGaps } from '../i18n-google/gapFill.ts'
import { googleToForLocale, protectPlaceholders, restorePlaceholders } from '../i18n-google/googleBatch.ts'
import { isKeepFill } from '../i18n-google/keepFill.ts'

describe('i18n-google keep-fill', () => {
  it('keeps brands, shortcuts, and empty slots', () => {
    expect(isKeepFill('MindGraph')).toBe(true)
    expect(isKeepFill('Ctrl+Enter')).toBe(true)
    expect(isKeepFill('{n}')).toBe(true)
    expect(isKeepFill('Log in to use this area')).toBe(false)
  })
})

describe('i18n-google placeholders', () => {
  it('round-trips interpolation slots', () => {
    const { text, tokens } = protectPlaceholders('Hello {name}, you have {n}')
    expect(text).toBe('Hello __MG_0__, you have __MG_1__')
    expect(restorePlaceholders('你好 __MG_0__，你有 __MG_1__', tokens)).toBe(
      '你好 {name}，你有 {n}'
    )
  })
})

describe('i18n-google googleToForLocale', () => {
  it('maps Tamil and Tagalog to Google targets', () => {
    expect(googleToForLocale('ta', 'ta')).toBe('ta')
    expect(googleToForLocale('tl', 'fil')).toBe('tl')
    expect(googleToForLocale('pt', 'pt-BR')).toBe('pt')
  })
})

describe('i18n-google collectGaps', () => {
  it('only queues keys that still equal English and have zh source', () => {
    const { gaps, out } = collectGaps(
      {
        login: 'Log in',
        brand: 'MindGraph',
        done: 'முடிந்தது',
      },
      {
        login: 'Log in',
        brand: 'MindGraph',
        done: 'Done',
      },
      {
        login: '登录',
        brand: 'MindGraph',
        done: '完成',
      }
    )
    expect(gaps).toEqual([{ key: 'login', zhText: '登录' }])
    expect(out.done).toBe('முடிந்தது')
  })
})
