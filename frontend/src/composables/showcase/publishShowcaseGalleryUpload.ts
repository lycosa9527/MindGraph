/**
 * Gallery upload retry helpers for Showcase publish.
 */
import {
  getShowcasePost,
  updateShowcasePost,
  uploadShowcaseGalleryImages,
  type ShowcasePost,
} from '@/utils/apiClient'

export function countResolvedGalleryImages(post: {
  gallery_items?: Array<{ kind: string; url?: string | null; missing?: boolean }>
}): number {
  return (
    post.gallery_items?.filter(
      (item) => item.kind === 'image' && item.url && !item.missing
    ).length ?? 0
  )
}

export async function buildGalleryRetryFormData(
  post: ShowcasePost,
  drafts: Array<{ file: File; filename: string }>
): Promise<FormData> {
  const formData = new FormData()
  formData.append('title', post.title)
  formData.append('description', post.description ?? '')
  formData.append('tags', JSON.stringify(post.tags ?? []))
  formData.append('case_type', post.case_type)
  formData.append('subject', post.subject ?? '')
  formData.append('grade', post.grade ?? '')
  if (post.diagram_type) {
    formData.append('diagram_type', post.diagram_type)
  }

  let specObj: Record<string, unknown> = { type: post.case_type, source: 'gallery' }
  if (post.spec_json_url) {
    const specRes = await fetch(post.spec_json_url, { credentials: 'include' })
    if (specRes.ok) {
      const parsed: unknown = await specRes.json()
      if (parsed && typeof parsed === 'object') {
        specObj = parsed as Record<string, unknown>
      }
    }
  }
  formData.append('spec', JSON.stringify(specObj))
  for (const draft of drafts) {
    formData.append('gallery_images', draft.file, draft.filename)
  }
  return formData
}

export async function ensureGalleryImagesPersisted(
  postId: string,
  drafts: Array<{ file: File; filename: string }>,
  messages: { uploadFailed: string; reuploadHint: string },
): Promise<void> {
  if (drafts.length === 0) return

  let post = await getShowcasePost(postId)
  if (countResolvedGalleryImages(post) >= drafts.length) return

  const uploadFormData = new FormData()
  for (const draft of drafts) {
    uploadFormData.append('gallery_images', draft.file, draft.filename)
  }
  let dedicatedEndpointFailed = false
  try {
    const uploaded = await uploadShowcaseGalleryImages(postId, uploadFormData)
    post = uploaded.post
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    const endpointUnavailable =
      message.includes('405') ||
      message.includes('404') ||
      message.toLowerCase().includes('not found') ||
      message.toLowerCase().includes('method not allowed')
    if (!endpointUnavailable) {
      throw error
    }
    dedicatedEndpointFailed = true
    post = await getShowcasePost(postId)
  }

  if (countResolvedGalleryImages(post) < drafts.length) {
    const retryForm = await buildGalleryRetryFormData(post, drafts)
    const updated = await updateShowcasePost(postId, retryForm)
    post = updated.post
  }

  if (countResolvedGalleryImages(post) < drafts.length) {
    const hint = dedicatedEndpointFailed ? messages.reuploadHint : ''
    throw new Error(
      hint ? `${messages.uploadFailed} ${hint}` : messages.uploadFailed
    )
  }
}
