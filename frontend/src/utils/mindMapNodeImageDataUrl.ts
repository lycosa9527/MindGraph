/**
 * Compress a picked image into a size-capped data URL for node adornments.
 */
import { resizeImageFileForVisionUpload } from '@/composables/media/resizeImageFileForVisionUpload'
import {
  MINDMAP_NODE_IMAGE_MAX_DATA_URL_CHARS,
  isMindMapImageDataUrlOverCap,
} from '@/utils/mindMapAdornments'

const NODE_IMAGE_MAX_LONG_EDGE = 480
const NODE_IMAGE_JPEG_QUALITY = 0.78

export async function mindMapNodeImageFileToDataUrl(file: File): Promise<string | null> {
  const resized = await resizeImageFileForVisionUpload(file, {
    maxLongEdge: NODE_IMAGE_MAX_LONG_EDGE,
    jpegQuality: NODE_IMAGE_JPEG_QUALITY,
    skipBelowBytes: 40 * 1024,
  })
  const dataUrl = await readFileAsDataUrl(resized)
  if (!dataUrl || isMindMapImageDataUrlOverCap(dataUrl)) return null
  if (dataUrl.length > MINDMAP_NODE_IMAGE_MAX_DATA_URL_CHARS) return null
  return dataUrl
}

function readFileAsDataUrl(file: File): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve(typeof reader.result === 'string' ? reader.result : null)
    }
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(file)
  })
}
