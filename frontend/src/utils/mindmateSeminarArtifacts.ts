/** Room-level seminar artifacts collected from persisted chat text. */

const DIAGRAM_PREVIEW_RE =
  /!\[([^\]]*)]\([^)]*(\/temp_images\/(dingtalk_([a-f0-9]{8})_\d+\.png))[^)]*\)/gi

/** Markdown links / bare URLs for docs produced during the seminar chat. */
const DOC_LINK_RE =
  /\[([^\]]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>"']+\.(?:pdf|docx?|pptx?|xlsx?|md|txt)(?:\?[^\s<>"']*)?)/gi

const DOC_EXT_RE = /\.(pdf|docx?|pptx?|xlsx?|md|txt)(?:$|\?)/i

export interface SeminarDiagramArtifact {
  previewId: string
  label: string
  messageId: number | null
  /** Absolute or root-relative path segment for `/api/temp_images/...`. */
  imagePath: string
}

export interface SeminarDocumentArtifact {
  id: string
  title: string
  url: string
  messageId: number | null
  /** Conversation attachment stored with the seminar, not a remote link. */
  backgroundFileId?: string
}

export function collectSeminarDiagramArtifacts(
  messages: ReadonlyArray<{ id?: number; content: string }>
): SeminarDiagramArtifact[] {
  const seen = new Set<string>()
  const found: SeminarDiagramArtifact[] = []
  for (const message of messages) {
    const source = message.content || ''
    DIAGRAM_PREVIEW_RE.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = DIAGRAM_PREVIEW_RE.exec(source)) !== null) {
      const previewId = match[4].toLowerCase()
      if (seen.has(previewId)) {
        continue
      }
      seen.add(previewId)
      const label = (match[1] || '').trim()
      const filename = match[3]
      found.push({
        previewId,
        label,
        messageId: message.id ?? null,
        imagePath: `/api/temp_images/${filename}`,
      })
    }
  }
  return found
}

function looksLikeDocumentUrl(url: string): boolean {
  return DOC_EXT_RE.test(url)
}

function basenameFromUrl(url: string): string {
  try {
    const path = new URL(url, 'http://local').pathname
    const base = path.split('/').pop() || url
    return decodeURIComponent(base)
  } catch {
    return url
  }
}

/**
 * Document links written in the chat.
 * Files people drop into the conversation stay on the message until someone shelves them.
 */
export function collectSeminarDocumentArtifacts(
  messages: ReadonlyArray<{ id?: number; content: string }>
): SeminarDocumentArtifact[] {
  const seen = new Set<string>()
  const found: SeminarDocumentArtifact[] = []
  for (const message of messages) {
    const source = message.content || ''
    DOC_LINK_RE.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = DOC_LINK_RE.exec(source)) !== null) {
      const label = (match[1] || '').trim()
      const linked = (match[2] || match[3] || '').trim()
      if (!linked || !looksLikeDocumentUrl(linked)) {
        continue
      }
      // Skip MindGraph diagram preview images already covered by diagrams.
      if (/\/temp_images\/dingtalk_/i.test(linked)) {
        continue
      }
      const key = linked.toLowerCase()
      if (seen.has(key)) {
        continue
      }
      seen.add(key)
      found.push({
        id: key,
        title: label || basenameFromUrl(linked),
        url: linked,
        messageId: message.id ?? null,
      })
    }
  }
  return found
}
