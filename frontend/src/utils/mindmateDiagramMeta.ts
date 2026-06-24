/** Parse diagram library metadata embedded in MindMate assistant markdown. */

import { rewriteMindmateTempImageUrls } from '@/utils/mindmateTempImageUrl'

export { rewriteMindmateTempImageUrls } from '@/utils/mindmateTempImageUrl'

const DIAGRAM_ID_COMMENT_RE = /<!--\s*mg-diagram-id:([a-f0-9-]+)\s*-->/i
const DIAGRAM_ID_COMMENT_STRIP_RE = /<!--\s*mg-diagram-id:[a-f0-9-]+\s*-->\s*/gi
const DIAGRAM_ID_ALT_RE = /!\[mg:([a-f0-9-]+)\]/i
const DIAGRAM_ID_URL_RE = /[?&]mgdid=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i
const GENERATED_DIAGRAM_IMAGE_RE =
  /!\[[^\]]*\]\([^)]*\/temp_images\/dingtalk_[a-f0-9]+_\d+\.png/i
const DINGTALK_PREVIEW_UNIQUE_ID_RE = /\/temp_images\/dingtalk_([a-f0-9]{8})_\d+\.png/i
const LIBRARY_SAVE_SKIP_NOTICE_RE =
  /(?:Diagram preview only|导图仅预览|library save failed|图库保存失败|图库已满|library is full|绑定钉钉|bind DingTalk|X-MG-Dify-User|Link DingTalk|联系.*管理员|MindBot 配置)/i
const LIBRARY_FULL_NOTICE_RE = /(?:图库已满|library is full)/i
const MARKDOWN_IMAGE_SRC_RE = /!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/i
const IMAGE_ONLY_ANSWER_RE = /^\s*!\[[^\]]*\]\([^)]+\)\s*$/

/** Return saved library diagram uuid embedded in assistant markdown, if any. */
export function parseMindmateDiagramLibraryId(content: string): string | null {
  const text = (content || '').trim()
  if (!text) {
    return null
  }

  const commentMatch = DIAGRAM_ID_COMMENT_RE.exec(text)
  if (commentMatch?.[1]) {
    return commentMatch[1]
  }

  const altMatch = DIAGRAM_ID_ALT_RE.exec(text)
  if (altMatch?.[1]) {
    return altMatch[1]
  }

  const urlMatch = DIAGRAM_ID_URL_RE.exec(text)
  if (urlMatch?.[1]) {
    return urlMatch[1]
  }

  return null
}

/** Remove embedded library-id HTML comments before rendering assistant markdown. */
export function stripMindmateDiagramIdComments(content: string): string {
  return (content || '').replace(DIAGRAM_ID_COMMENT_STRIP_RE, '').trimEnd()
}

/** First markdown image src in assistant content (same-origin rewrite applied when pageHost set). */
export function extractFirstMarkdownImageUrl(content: string, pageHost?: string): string | null {
  const text = stripMindmateDiagramIdComments(content || '')
  const match = MARKDOWN_IMAGE_SRC_RE.exec(text)
  if (!match?.[1]) {
    return null
  }
  const placeholder = `![x](${match[1]})`
  const rewritten = rewriteMindmateTempImageUrls(placeholder, pageHost)
  const rewrittenMatch = MARKDOWN_IMAGE_SRC_RE.exec(rewritten)
  return rewrittenMatch?.[1]?.trim() ?? match[1].trim()
}

/** True when assistant markdown is essentially a single image (no surrounding prose). */
export function isImagePrimaryAnswer(content: string): boolean {
  const text = stripMindmateDiagramIdComments(content || '').trim()
  if (!text) {
    return false
  }
  const withoutNotices = text
    .replace(LIBRARY_SAVE_SKIP_NOTICE_RE, '')
    .replace(LIBRARY_FULL_NOTICE_RE, '')
    .trim()
  return IMAGE_ONLY_ANSWER_RE.test(withoutNotices)
}

/** True when markdown includes a MindGraph generate_dingtalk preview image. */
export function hasGeneratedDiagramImage(content: string): boolean {
  return GENERATED_DIAGRAM_IMAGE_RE.test((content || '').trim())
}

/** Temp PNG id from generate_dingtalk preview URL (for skip-metadata lookup). */
export function extractMindmatePreviewUniqueId(content: string): string | null {
  const match = DINGTALK_PREVIEW_UNIQUE_ID_RE.exec((content || '').trim())
  return match?.[1] ?? null
}

/** Backend already appended a skip notice in assistant markdown. */
export function hasLibrarySaveSkipNotice(content: string): boolean {
  return LIBRARY_SAVE_SKIP_NOTICE_RE.test((content || '').trim())
}

/** Backend notice indicates diagram library quota is full. */
export function hasLibraryFullNotice(content: string): boolean {
  return LIBRARY_FULL_NOTICE_RE.test((content || '').trim())
}

/** Preview image present but library uuid missing — canvas entry unavailable. */
export function needsLibrarySaveHint(content: string): boolean {
  const text = (content || '').trim()
  return (
    hasGeneratedDiagramImage(text) &&
    parseMindmateDiagramLibraryId(text) === null &&
    !hasLibrarySaveSkipNotice(text)
  )
}

/** Show library-full hint when embedded notice exists but no saved uuid. */
export function needsLibraryFullHint(content: string): boolean {
  const text = (content || '').trim()
  return (
    hasGeneratedDiagramImage(text) &&
    parseMindmateDiagramLibraryId(text) === null &&
    hasLibraryFullNotice(text)
  )
}
