import { describe, expect, it } from 'vitest'

import { renderRichMarkdownHtmlImpl } from '@/composables/core/markdownRenderer'

describe('workshop markdown fences', () => {
  it('renders pipe tables', () => {
    const html = renderRichMarkdownHtmlImpl('| A | B |\n| --- | --- |\n| 1 | 2 |')
    expect(html).toContain('<table>')
    expect(html).toContain('<th>')
    expect(html).toContain('A')
  })

  it('renders strikethrough', () => {
    const html = renderRichMarkdownHtmlImpl('~~gone~~')
    expect(html).toMatch(/<del>gone<\/del>|<s>gone<\/s>/)
  })

  it('renders Zulip quote fences as blockquotes', () => {
    const html = renderRichMarkdownHtmlImpl('```quote\nhello\n```')
    expect(html).toContain('<blockquote')
    expect(html).toContain('hello')
  })

  it('renders Zulip spoiler fences as details', () => {
    const html = renderRichMarkdownHtmlImpl('```spoiler Answer\nhidden\n```')
    expect(html).toContain('<details')
    expect(html).toContain('<summary>Answer</summary>')
    expect(html).toContain('hidden')
  })

  it('keeps markdown images so library diagrams show in messages', () => {
    const html = renderRichMarkdownHtmlImpl(
      '![mg:550e8400-e29b-41d4-a716-446655440000](/api/chat/attachments/3/download)'
    )
    expect(html).toContain('<img')
    expect(html).toContain('/api/chat/attachments/3/download')
  })
})
