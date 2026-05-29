/** Vitest: lazy markdown route helpers and ready flag */
import { describe, expect, it } from 'vitest'

import { markdownRendererReady, routeUsesRichMarkdown } from '@/composables/core/lazyMarkdown'

describe('routeUsesRichMarkdown', () => {
  it('matches markdown-heavy app routes', () => {
    expect(routeUsesRichMarkdown('/mindmate')).toBe(true)
    expect(routeUsesRichMarkdown('/workshop-chat')).toBe(true)
    expect(routeUsesRichMarkdown('/m/mindmate')).toBe(true)
    expect(routeUsesRichMarkdown('/canvas')).toBe(true)
  })

  it('skips admin and auth routes', () => {
    expect(routeUsesRichMarkdown('/admin')).toBe(false)
    expect(routeUsesRichMarkdown('/auth')).toBe(false)
  })
})

describe('markdownRendererReady', () => {
  it('is a boolean ref', () => {
    expect(typeof markdownRendererReady.value).toBe('boolean')
  })
})
