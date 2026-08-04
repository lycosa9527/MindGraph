/**
 * Gallery upload helpers for Showcase publish.
 *
 * Completeness must be checked on ``spec.gallery[].path`` — not
 * ``gallery_items[].url``. Formatted URLs can resolve from storage even when
 * the JSONB ``path`` field was never persisted (approve then fails).
 */
import { getShowcasePost } from '@/utils/apiClient'

export function countGalleryImagePathsInSpec(spec: unknown): number {
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) return 0
  const gallery = (spec as { gallery?: unknown }).gallery
  if (!Array.isArray(gallery)) return 0
  return gallery.filter((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false
    const entry = item as { kind?: unknown; path?: unknown }
    return (
      entry.kind === 'image' &&
      typeof entry.path === 'string' &&
      entry.path.trim().length > 0
    )
  }).length
}

export async function ensureGalleryImagesPersisted(
  postId: string,
  expectedImageCount: number,
  messages: { uploadFailed: string; reuploadHint: string },
): Promise<void> {
  if (expectedImageCount <= 0) return

  const post = await getShowcasePost(postId)
  if (countGalleryImagePathsInSpec(post.spec) >= expectedImageCount) return

  throw new Error(
    messages.reuploadHint
      ? `${messages.uploadFailed} ${messages.reuploadHint}`
      : messages.uploadFailed,
  )
}
