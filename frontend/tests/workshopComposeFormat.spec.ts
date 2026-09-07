import { describe, expect, it } from 'vitest'

import { applyComposeFormat, insertTextAtCursor } from '@/utils/workshopComposeFormat'
import { buildWorkshopDiagramMarkdown } from '@/utils/workshopDiagramEmbed'
import { buildWorkshopRoleMarkdown, inlineWorkshopRoleMarkdown } from '@/utils/workshopRoleEmbed'

describe('applyComposeFormat', () => {
  it('wraps a selection in bold', () => {
    const result = applyComposeFormat('hello world', 6, 11, 'bold')
    expect(result.text).toBe('hello **world**')
    expect(result.start).toBe(8)
    expect(result.end).toBe(13)
  })

  it('inserts a bulleted list on the current line', () => {
    const result = applyComposeFormat('apple', 0, 5, 'bulleted')
    expect(result.text).toBe('- apple')
  })

  it('toggles bullets off when already marked', () => {
    const result = applyComposeFormat('- apple', 0, 7, 'bulleted')
    expect(result.text).toBe('apple')
  })

  it('numbers selected lines', () => {
    const result = applyComposeFormat('a\nb', 0, 3, 'numbered')
    expect(result.text).toBe('1. a\n2. b')
  })

  it('wraps a quote fence', () => {
    const result = applyComposeFormat('note', 0, 4, 'quote')
    expect(result.text).toBe('```quote\nnote\n```')
  })

  it('wraps a spoiler fence', () => {
    const result = applyComposeFormat('secret', 0, 6, 'spoiler')
    expect(result.text).toBe('```spoiler \nsecret\n```')
  })

  it('uses inline latex for a single-line selection', () => {
    const result = applyComposeFormat('E=mc^2', 0, 6, 'latex')
    expect(result.text).toBe('$$E=mc^2$$')
  })

  it('inserts a markdown table', () => {
    const result = applyComposeFormat('', 0, 0, 'table')
    expect(result.text).toContain('| A | B |')
    expect(result.text).toContain('| --- | --- |')
  })
})

describe('insertTextAtCursor', () => {
  it('inserts at the caret', () => {
    const result = insertTextAtCursor('ab', 1, 1, '🙂')
    expect(result.text).toBe('a🙂b')
    expect(result.start).toBe(3)
  })
})

describe('buildWorkshopDiagramMarkdown', () => {
  it('embeds a library uuid in alt text and a comment', () => {
    const id = '550e8400-e29b-41d4-a716-446655440000'
    const md = buildWorkshopDiagramMarkdown(id, '背影', '/api/chat/attachments/9/download')
    expect(md).toBe(`![mg:${id}](/api/chat/attachments/9/download)\n<!-- mg-diagram-id:${id} -->`)
  })

  it('falls back to the title when the id is not a uuid', () => {
    const md = buildWorkshopDiagramMarkdown('local', 'My map', '/api/chat/attachments/1/download')
    expect(md).toBe('![My map](/api/chat/attachments/1/download)')
  })
})

describe('buildWorkshopRoleMarkdown', () => {
  it('embeds the Course Builder role asset url', () => {
    const md = buildWorkshopRoleMarkdown('11-clap', 'Clap')
    expect(md).toBe('![Clap](/api/training/assets/roles/11-clap.webp)')
  })

  it('falls back to look-here for an unknown role id', () => {
    const md = buildWorkshopRoleMarkdown('ghost', 'Ghost')
    expect(md).toBe('![Ghost](/api/training/assets/roles/01-look-here.webp)')
  })
})

describe('inlineWorkshopRoleMarkdown', () => {
  it('joins a role clip to neighboring words on one line', () => {
    const src = '123\n![Clap](/api/training/assets/roles/11-clap.webp)\n测试23'
    expect(inlineWorkshopRoleMarkdown(src)).toBe(
      '123 ![Clap](/api/training/assets/roles/11-clap.webp) 测试23'
    )
  })

  it('leaves a lone role clip unchanged', () => {
    const src = '![Clap](/api/training/assets/roles/11-clap.webp)'
    expect(inlineWorkshopRoleMarkdown(src)).toBe(src)
  })
})
