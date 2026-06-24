/** Copy MindMate assistant messages — image bytes for diagram answers, text otherwise. */

import {
  extractFirstMarkdownImageUrl,
  hasGeneratedDiagramImage,
  isImagePrimaryAnswer,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'

function resolveAbsoluteUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) {
    return url
  }
  if (typeof window === 'undefined') {
    return url
  }
  const path = url.startsWith('/') ? url : `/${url}`
  return `${window.location.origin}${path}`
}

async function copyImageUrlToClipboard(imageUrl: string): Promise<boolean> {
  if (typeof ClipboardItem === 'undefined' || !navigator.clipboard?.write) {
    return false
  }

  const response = await fetch(resolveAbsoluteUrl(imageUrl), { credentials: 'same-origin' })
  if (!response.ok) {
    return false
  }

  const blob = await response.blob()
  const type = blob.type.startsWith('image/') ? blob.type : 'image/png'
  const imageBlob = blob.type.startsWith('image/') ? blob : new Blob([await blob.arrayBuffer()], { type })

  await navigator.clipboard.write([new ClipboardItem({ [type]: imageBlob })])
  return true
}

/**
 * Copy assistant markdown: diagram/image answers copy the PNG; everything else copies text.
 */
export async function copyMindmateAssistantMessage(
  content: string,
  pageHost?: string
): Promise<void> {
  const text = (content || '').trim()
  if (!text) {
    await navigator.clipboard.writeText('')
    return
  }

  if (hasGeneratedDiagramImage(text) || isImagePrimaryAnswer(text)) {
    const imageUrl = extractFirstMarkdownImageUrl(text, pageHost)
    if (imageUrl && (await copyImageUrlToClipboard(imageUrl))) {
      return
    }
  }

  await navigator.clipboard.writeText(stripMindmateDiagramIdComments(text))
}
