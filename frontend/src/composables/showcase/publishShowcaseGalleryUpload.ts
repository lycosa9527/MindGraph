/**
 * Gallery upload helpers for Showcase publish (init → PUT → complete).
 */
import {
  uploadShowcaseFile,
  type ShowcaseUploadRole,
} from '@/composables/showcase/uploadShowcaseFile'
import { getShowcasePost, type ShowcasePost } from '@/utils/apiClient'

export function countResolvedGalleryImages(post: {
  gallery_items?: Array<{ kind: string; url?: string | null; missing?: boolean }>
}): number {
  return (
    post.gallery_items?.filter(
      (item) => item.kind === 'image' && item.url && !item.missing
    ).length ?? 0
  )
}

export async function ensureGalleryImagesPersisted(
  postId: string,
  drafts: Array<{ file: File; filename: string }>,
  messages: { uploadFailed: string; reuploadHint: string },
): Promise<void> {
  if (drafts.length === 0) return

  let post = await getShowcasePost(postId)
  if (countResolvedGalleryImages(post) >= drafts.length) return

  const specObj =
    post.spec && typeof post.spec === 'object' && !Array.isArray(post.spec)
      ? (post.spec as { gallery?: unknown })
      : null
  const galleryList = Array.isArray(specObj?.gallery) ? specObj.gallery : []

  let draftIdx = 0
  for (let slot = 0; slot < Math.max(galleryList.length, drafts.length); slot += 1) {
    const entry = galleryList[slot] as { kind?: string; path?: string; pending?: boolean } | undefined
    const needsUpload =
      !entry || (entry.kind === 'image' && (!entry.path || entry.pending))
    if (!needsUpload) continue
    const draft = drafts[draftIdx]
    if (!draft) break
    draftIdx += 1
    await uploadShowcaseFile({
      postId,
      role: `gallery_${slot}` as ShowcaseUploadRole,
      file: draft.file,
      filename: draft.filename,
    })
  }

  // Fallback: upload remaining drafts into sequential slots
  while (draftIdx < drafts.length) {
    const draft = drafts[draftIdx]
    await uploadShowcaseFile({
      postId,
      role: `gallery_${draftIdx}` as ShowcaseUploadRole,
      file: draft.file,
      filename: draft.filename,
    })
    draftIdx += 1
  }

  post = await getShowcasePost(postId)
  if (countResolvedGalleryImages(post) < drafts.length) {
    throw new Error(
      messages.reuploadHint
        ? `${messages.uploadFailed} ${messages.reuploadHint}`
        : messages.uploadFailed,
    )
  }
}
