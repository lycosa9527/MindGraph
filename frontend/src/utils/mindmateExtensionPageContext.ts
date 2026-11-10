/**
 * Chrome extension MindMate first messages embed page extraction in Dify query.
 * Canvas diagram context uses the same split: the model sees the outline,
 * the bubble shows only the teacher's question.
 */
import { MINDMATE_DIAGRAM_CONTEXT_MARKER } from '@/utils/mindmateDiagramBrief'

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

function questionAfterDiagramBrief(text: string): string | null {
  if (!text.startsWith(MINDMATE_DIAGRAM_CONTEXT_MARKER)) {
    return null
  }
  const splitAt = text.indexOf('\n\n')
  if (splitAt < 0) {
    return null
  }
  const question = text.slice(splitAt + 2).trim()
  return question || null
}

/** Teacher-visible question. Diagram outlines and extension payloads stay off the bubble. */
export function displayMindmateUserQueryForUi(query: string | undefined | null): string {
  const text = (query || '').trim()
  const diagramQuestion = questionAfterDiagramBrief(text)
  if (diagramQuestion) {
    return diagramQuestion
  }
  if (!text || !isExtensionPageContextMessage(text)) {
    return query || ''
  }
  const question = extractUserQuestionFromPageContext(text)
  return question || text
}
