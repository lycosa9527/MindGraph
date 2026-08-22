import { describe, expect, it } from 'vitest'

import { sanitizeMarkdownItHtml } from '@/composables/core/markdownKatexSanitize'

describe('sanitizeMarkdownItHtml', () => {
  it('keeps blob: img src used by MindMate diagram preview cache', () => {
    const html = sanitizeMarkdownItHtml(
      '<p><img src="blob:http://localhost:41732/abc-123" alt="mg:x"></p>'
    )
    expect(html).toContain('blob:http://localhost:41732/abc-123')
    expect(html).toContain('<img')
  })

  it('keeps same-origin temp image src with signed query', () => {
    const html = sanitizeMarkdownItHtml(
      '<img src="/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&amp;exp=1" alt="">'
    )
    expect(html).toContain('/api/temp_images/dingtalk_deadbeef_1710000000.png')
    expect(html).toContain('sig=x')
  })

  it('strips javascript: img src', () => {
    const html = sanitizeMarkdownItHtml('<img src="javascript:alert(1)" alt="x">')
    expect(html).not.toContain('javascript:')
  })
})
