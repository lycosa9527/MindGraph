/** Copy MindMate assistant messages — image bytes for diagram answers, text otherwise. */

import {
  hasGeneratedDiagramImage,
  isImagePrimaryAnswer,
  parseMindmateDiagramLibraryId,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'
import { resolveMindmateDiagramPreviewBlob } from '@/utils/mindmateDiagramPreviewResolve'

async function copyBlobToClipboard(blob: Blob): Promise<boolean> {
  if (typeof ClipboardItem === 'undefined' || !navigator.clipboard?.write) {
    return false
  }
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
    const blob = await resolveMindmateDiagramPreviewBlob({
      content: text,
      pageHost,
      libraryDiagramId: parseMindmateDiagramLibraryId(text),
    })
    if (blob && (await copyBlobToClipboard(blob))) {
      return
    }
  }

  await navigator.clipboard.writeText(stripMindmateDiagramIdComments(text))
}
