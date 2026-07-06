/**
 * Chrome extension MindMate first messages embed page extraction in Dify query.
 * Display layers should show only the teacher's question, not the full payload.
 */

const MATERIAL_HEADER_MARKERS = [
  '**【参考材料：网页正文】**',
  '**【參考材料：網頁正文】**',
  '**[Reference material: page body]**',
] as const

const PAGE_CONTEXT_INTRO_MARKERS = [
  'MindGraph extension · page context',
  'MindGraph 浏览器扩展 · 网页上下文',
  'MindGraph 瀏覽器擴充 · 網頁上下文',
] as const

const USER_QUESTION_LINE_RES = [
  /^\*\*用户问题[^*]*\*\*\s*(.*)$/m,
  /^\*\*使用者問題[^*]*\*\*\s*(.*)$/m,
  /^\*\*User question[^*]*\*\*\s*(.*)$/im,
] as const

function isExtensionPageContextMessage(text: string): boolean {
  if (MATERIAL_HEADER_MARKERS.some((marker) => text.includes(marker))) {
    return true
  }
  return PAGE_CONTEXT_INTRO_MARKERS.some((marker) => text.includes(marker))
}

function extractUserQuestionFromPageContext(text: string): string | null {
  for (const pattern of USER_QUESTION_LINE_RES) {
    const match = pattern.exec(text)
    if (match?.[1]) {
      const question = match[1].trim()
      if (question) {
        return question
      }
    }
  }
  return null
}

/** Return the teacher-visible question when query is an extension page-context payload. */
export function displayMindmateUserQueryForUi(query: string | undefined | null): string {
  const text = (query || '').trim()
  if (!text || !isExtensionPageContextMessage(text)) {
    return query || ''
  }
  const question = extractUserQuestionFromPageContext(text)
  return question || text
}
