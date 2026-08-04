/**
 * Build a File suitable for MindMate / Dify upload from a Showcase case.
 *
 * Prefer the teaching-doc attachment (or LibreOffice preview.pdf); if neither
 * exists, synthesize a markdown brief from case text fields so MindMate still
 * receives case context as a pending attachment.
 */
import { fetchShowcaseAsset } from '@/utils/fetchShowcaseAsset'
import type { ShowcasePost } from '@/utils/apiClient'

type TeachingSpec = {
  body?: string
  design_highlights?: string[] | string
  teaching_reflection?: string
  attachment_filename?: string
}

const MIME_BY_EXT: Record<string, string> = {
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  txt: 'text/plain',
  md: 'text/markdown',
  markdown: 'text/markdown',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
}

function extensionOf(nameOrUrl: string): string {
  const path = nameOrUrl.split('?')[0] ?? ''
  const base = path.split('/').pop() ?? ''
  const dot = base.lastIndexOf('.')
  if (dot < 0) return ''
  return base.slice(dot + 1).toLowerCase()
}

function mimeForName(name: string, fallback = 'application/octet-stream'): string {
  return MIME_BY_EXT[extensionOf(name)] ?? fallback
}

function filenameFromUrl(url: string, fallback: string): string {
  const path = url.split('?')[0] ?? ''
  const base = decodeURIComponent(path.split('/').pop() || '')
  if (base && base.includes('.')) return base
  return fallback
}

function safeFilenameStem(title: string): string {
  const cleaned = title
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '')
    .replace(/\s+/g, ' ')
    .slice(0, 80)
  return cleaned || 'showcase-case'
}

function asTeachingSpec(spec: unknown): TeachingSpec {
  if (!spec || typeof spec !== 'object') return {}
  return spec as TeachingSpec
}

function highlightsToLines(raw: TeachingSpec['design_highlights']): string[] {
  if (Array.isArray(raw)) return raw.map((s) => String(s).trim()).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
}

export function formatShowcaseCaseMarkdown(post: ShowcasePost & { spec?: unknown }): string {
  const spec = asTeachingSpec(post.spec)
  const body =
    (typeof spec.body === 'string' && spec.body.trim()) ||
    (typeof post.description === 'string' && post.description.trim()) ||
    ''
  const highlights = highlightsToLines(spec.design_highlights)
  const reflection =
    typeof spec.teaching_reflection === 'string' ? spec.teaching_reflection.trim() : ''

  const lines: string[] = [`# ${post.title.trim() || '教学设计案例'}`]
  if (post.subject?.trim()) lines.push(`- 学科：${post.subject.trim()}`)
  if (post.grade?.trim()) lines.push(`- 年级：${post.grade.trim()}`)
  if (body) {
    lines.push('', '## 案例简介', body)
  }
  if (highlights.length > 0) {
    lines.push('', '## 设计亮点', ...highlights.map((h) => `- ${h}`))
  }
  if (reflection) {
    lines.push('', '## 教学反思', reflection)
  }
  return `${lines.join('\n').trim()}\n`
}

function pickAttachmentUrl(post: ShowcasePost): string | null {
  const attachment = post.attachment_url?.trim()
  if (attachment) return attachment
  const preview = post.preview_url?.trim()
  if (preview) return preview
  return null
}

export async function buildShowcaseMindMateAttachment(
  post: ShowcasePost & { spec?: unknown }
): Promise<File> {
  const stem = safeFilenameStem(post.title)
  const url = pickAttachmentUrl(post)
  if (url) {
    const response = await fetchShowcaseAsset(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch showcase attachment (${response.status})`)
    }
    const blob = await response.blob()
    const spec = asTeachingSpec(post.spec)
    const preferredName =
      (typeof spec.attachment_filename === 'string' && spec.attachment_filename.trim()) ||
      filenameFromUrl(url, `${stem}.pdf`)
    const type = blob.type && blob.type !== 'application/octet-stream'
      ? blob.type
      : mimeForName(preferredName)
    return new File([blob], preferredName, { type })
  }

  const markdown = formatShowcaseCaseMarkdown(post)
  return new File([markdown], `${stem}.md`, { type: 'text/markdown' })
}
