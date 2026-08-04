/**
 * Showcase moderation media_status labels and chip styles.
 */
import type { ShowcasePost } from '@/utils/apiClient'

export type ShowcaseMediaStatus =
  | 'awaiting_upload'
  | 'converting_preview'
  | 'preview_ready'
  | 'cover_ready'
  | 'ready'
  | 'conversion_failed'

const OFFICE_PREVIEW_SUFFIXES = ['.pptx', '.docx', '.doc'] as const

function pathFromUrl(url: string | null | undefined): string {
  return (url || '').toLowerCase().split('?')[0] || ''
}

function teachingNeedsOfficePreview(post: ShowcasePost): boolean {
  if (post.case_type !== 'teaching_design' || post.preview_url) return false
  const path = pathFromUrl(post.attachment_url)
  return OFFICE_PREVIEW_SUFFIXES.some((suffix) => path.endsWith(suffix))
}

/** Prefer API media_status; fall back to URL/path derivation for older payloads. */
export function resolveShowcaseMediaStatus(post: ShowcasePost): ShowcaseMediaStatus {
  if (post.media_status) return post.media_status

  if (post.case_type === 'teaching_design') {
    if (!post.attachment_url) return 'awaiting_upload'
    if (teachingNeedsOfficePreview(post)) return 'converting_preview'
    if (!post.thumbnail_url) return 'preview_ready'
    return 'cover_ready'
  }

  const galleryPending = (post.gallery_items || []).some(
    (item) => item.kind === 'image' && (item.missing || !item.url)
  )
  if (galleryPending) return 'awaiting_upload'
  if (post.thumbnail_url) return 'cover_ready'
  return 'ready'
}

export function showcaseMediaStatusLabelKey(status: ShowcaseMediaStatus): string {
  return `admin.showcase.mediaStatus.${status}`
}

export function showcaseMediaStatusChipClass(status: ShowcaseMediaStatus): string {
  if (status === 'awaiting_upload') return 'bg-gray-100 text-gray-600'
  if (status === 'converting_preview') return 'bg-amber-50 text-amber-800'
  if (status === 'preview_ready') return 'bg-sky-50 text-sky-800'
  if (status === 'conversion_failed') return 'bg-red-50 text-red-700'
  return 'bg-emerald-50 text-emerald-800'
}
