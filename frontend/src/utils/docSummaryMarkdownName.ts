/**
 * Derive a user-facing markdown filename from a Document Summary source name.
 * COS still stores a fixed `extracted.md`; this is display-only.
 */

const SOURCE_EXT =
  /\.(pdf|docx?|pptx?|xlsx?|txt|md|csv|jpe?g|png|webp|mp3|wav|m4a|aac|flac|ogg|opus|amr|wma)$/i

export function toDocSummaryMarkdownName(fileName: string | null | undefined): string {
  const raw = (fileName || '').trim()
  if (!raw) return 'document.md'

  const base = raw.includes('/') || raw.includes('\\')
    ? raw.split(/[/\\]/).pop() || raw
    : raw

  const withoutExt = base.replace(SOURCE_EXT, '').trim() || 'document'
  if (withoutExt.toLowerCase().endsWith('.md')) {
    return withoutExt
  }
  return `${withoutExt}.md`
}

export function docSummarySourceLabel(fileName: string | null | undefined): string | null {
  const raw = (fileName || '').trim()
  if (!raw) return null
  const base = raw.includes('/') || raw.includes('\\')
    ? raw.split(/[/\\]/).pop() || raw
    : raw
  return base || null
}
