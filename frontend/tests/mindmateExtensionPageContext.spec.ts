import { describe, expect, it } from 'vitest'

import { displayMindmateUserQueryForUi } from '@/utils/mindmateExtensionPageContext'

const SAMPLE_COMPOSED = [
  '【MindGraph 浏览器扩展 · 网页上下文】用户正在 Chrome/Edge 中浏览网页。',
  '',
  '**用户问题（意图分类与回答请以本句为准）：** 请分析这节阅读课',
  '',
  '【路由说明】意图分类、知识检索与回答均以上方「用户问题」为准。',
  '',
  '**页面标题：** 示例课',
  '**页面 URL：** https://example.com/lesson',
  '',
  '**【参考材料：网页正文】**',
  '',
  '## 课文正文',
  '',
  '很长的提取正文内容……',
].join('\n')

describe('displayMindmateUserQueryForUi', () => {
  it('returns plain queries unchanged', () => {
    expect(displayMindmateUserQueryForUi('你好')).toBe('你好')
    expect(displayMindmateUserQueryForUi('')).toBe('')
  })

  it('extracts the teacher question from extension page-context payloads', () => {
    expect(displayMindmateUserQueryForUi(SAMPLE_COMPOSED)).toBe('请分析这节阅读课')
  })

  it('supports English question markers', () => {
    const composed = [
      '[MindGraph extension · page context] intro',
      '',
      '**User question (classify intent and answer from this line):** Summarize this article',
      '',
      '**[Reference material: page body]**',
      '',
      'Article body',
    ].join('\n')
    expect(displayMindmateUserQueryForUi(composed)).toBe('Summarize this article')
  })

  it('supports Traditional Chinese question markers', () => {
    const composed = [
      'MindGraph 瀏覽器擴充 · 網頁上下文',
      '',
      '**使用者問題（意圖分類與回答請以本句為準）：** 這節課怎麼上？',
      '',
      '**【參考材料：網頁正文】**',
      '',
      '正文',
    ].join('\n')
    expect(displayMindmateUserQueryForUi(composed)).toBe('這節課怎麼上？')
  })
})
