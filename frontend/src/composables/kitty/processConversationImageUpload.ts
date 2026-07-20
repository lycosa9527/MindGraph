/**
 * Unified Kitty / one-sentence conversation image upload.
 * Hand-drawn → rebuild canvas + outline extract; text → OCR extract.
 */
import { resizeImageFileForVisionUpload } from '@/composables/media/resizeImageFileForVisionUpload'
import { apiUpload } from '@/utils/apiClient'

export type ConversationImageMode = 'handdrawn' | 'text'

export type ConversationImageResult = {
  mode: ConversationImageMode
  isMindmap: boolean
  topic?: string
  packageId?: number
  docSummarySaved: boolean
  ocrExcerpt?: string
  ocrText?: string
  spec?: Record<string, unknown>
  library?: {
    saved?: boolean
    desktop_queued?: boolean
  }
  appliedToLibrary: boolean
  desktopQueued: boolean
}

type ApiResult = {
  success?: boolean
  mode?: string
  is_mindmap?: boolean
  topic?: string
  package_id?: number
  doc_summary_saved?: boolean
  ocr_excerpt?: string
  ocr_text?: string
  spec?: Record<string, unknown>
  library?: {
    saved?: boolean
    desktop_queued?: boolean
  }
  detail?: string | { message?: string }
  error?: string
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) {
      return message
    }
  }
  return fallback
}

/**
 * Resize + POST /api/kitty/conversation_image for the active library diagram.
 */
export async function processConversationImageUpload(options: {
  file: File
  diagramId: string
  diagramTitle?: string
  language?: string
  applyToLibrary?: boolean
}): Promise<ConversationImageResult> {
  const diagramId = options.diagramId.trim()
  if (!diagramId) {
    throw new Error('diagram_id is required')
  }

  const resized = await resizeImageFileForVisionUpload(options.file)
  const formData = new FormData()
  formData.append('file', resized)
  formData.append('language', options.language || 'zh')
  formData.append('diagram_id', diagramId)
  if (options.diagramTitle?.trim()) {
    formData.append('diagram_title', options.diagramTitle.trim())
  }
  formData.append(
    'apply_to_library',
    options.applyToLibrary === false ? 'false' : 'true'
  )

  const response = await apiUpload('/api/kitty/conversation_image', formData)
  const result = (await response.json().catch(() => ({}))) as ApiResult
  if (!response.ok || !result.success) {
    throw new Error(
      detailMessage(result.detail, result.error || 'Image processing failed')
    )
  }

  const mode: ConversationImageMode =
    result.mode === 'handdrawn' ? 'handdrawn' : 'text'

  return {
    mode,
    isMindmap: mode === 'handdrawn',
    topic: typeof result.topic === 'string' ? result.topic : undefined,
    packageId:
      typeof result.package_id === 'number' ? result.package_id : undefined,
    docSummarySaved: Boolean(
      result.doc_summary_saved === true ||
        (typeof result.package_id === 'number' && result.package_id > 0)
    ),
    ocrExcerpt:
      typeof result.ocr_excerpt === 'string' ? result.ocr_excerpt : undefined,
    ocrText: typeof result.ocr_text === 'string' ? result.ocr_text : undefined,
    spec: result.spec,
    library: result.library,
    appliedToLibrary: Boolean(result.library?.saved),
    desktopQueued: Boolean(result.library?.desktop_queued),
  }
}
