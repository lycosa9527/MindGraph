import { ref } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  type PackageDetailResponse,
  fileCenterKeys,
} from '@/composables/fileCenter/useFileCenter'
import { resizeImageFileForVisionUpload } from '@/composables/media/resizeImageFileForVisionUpload'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import {
  DOC_SUMMARY_CONTENT_TOO_LONG_CODE,
  DOC_SUMMARY_MAX_INPUT_CHARS,
  DOC_SUMMARY_MAX_UPLOAD_BYTES,
  DOC_SUMMARY_PACKAGES_BASE,
  DOC_SUMMARY_STORAGE_CONFLICT_CODE,
} from '@/config/docSummaryApi'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import { useDiagramStore, useLLMResultsStore, useSavedDiagramsStore } from '@/stores'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { authFetch } from '@/utils/api'
import { apiRequestJson, apiUpload } from '@/utils/apiClient'
import { mergeMindMapPresentationExtrasIntoSpec } from '@/utils/mindMapLiveSpecExtras'

const PACKAGES_BASE = DOC_SUMMARY_PACKAGES_BASE

/** Paste / typed text hard cap (same as model input budget). */
export const MAX_CONTENT_LENGTH = DOC_SUMMARY_MAX_INPUT_CHARS
/** Upload file size gate. */
export const MAX_UPLOAD_BYTES = DOC_SUMMARY_MAX_UPLOAD_BYTES

/** File picker accept list for Document Summary lite uploads. */
export const DOC_SUMMARY_UPLOAD_ACCEPT =
  '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.csv,.jpg,.jpeg,.png,.webp,' +
  '.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.amr,.wma,' +
  'application/pdf,application/msword,' +
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document,' +
  'application/vnd.ms-powerpoint,' +
  'application/vnd.openxmlformats-officedocument.presentationml.presentation,' +
  'application/vnd.ms-excel,' +
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,' +
  'text/plain,text/markdown,text/csv,' +
  'image/jpeg,image/png,image/webp,' +
  'audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/flac,audio/ogg,audio/opus,audio/amr'

const ALLOWED_UPLOAD_EXTENSIONS = new Set([
  '.pdf',
  '.doc',
  '.docx',
  '.ppt',
  '.pptx',
  '.xls',
  '.xlsx',
  '.txt',
  '.md',
  '.csv',
  '.jpg',
  '.jpeg',
  '.png',
  '.webp',
  '.mp3',
  '.wav',
  '.m4a',
  '.aac',
  '.flac',
  '.ogg',
  '.opus',
  '.amr',
  '.wma',
])

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp'])

const EXTRACT_STAGE_I18N: Record<string, string> = {
  starting: 'canvas.mindMapDocumentSummary.stageStarting',
  converting: 'canvas.mindMapDocumentSummary.stageConverting',
  extracting: 'canvas.mindMapDocumentSummary.stageExtracting',
  ocr: 'canvas.mindMapDocumentSummary.stageOcr',
  transcribing: 'canvas.mindMapDocumentSummary.stageTranscribing',
  storing: 'canvas.mindMapDocumentSummary.stageStoring',
  completed: 'canvas.mindMapDocumentSummary.statusReady',
  failed: 'canvas.mindMapDocumentSummary.statusFailed',
  extracted: 'canvas.mindMapDocumentSummary.statusReady',
}

type WebContentResult = {
  success?: boolean
  spec?: Record<string, unknown>
  error?: string
  detail?: string | { code?: string; message?: string; max_chars?: number }
  is_mindmap?: boolean
  source?: string
  confidence?: number
  reason?: string
}

function isContentTooLongDetail(detail: WebContentResult['detail']): boolean {
  if (typeof detail === 'object' && detail !== null) {
    return detail.code === DOC_SUMMARY_CONTENT_TOO_LONG_CODE
  }
  if (typeof detail === 'string') {
    return detail.includes('model input limit') || detail.includes(DOC_SUMMARY_CONTENT_TOO_LONG_CODE)
  }
  return false
}

function isStorageConflictDetail(detail: WebContentResult['detail']): boolean {
  if (typeof detail === 'object' && detail !== null) {
    return detail.code === DOC_SUMMARY_STORAGE_CONFLICT_CODE
  }
  if (typeof detail === 'string') {
    return detail.includes(DOC_SUMMARY_STORAGE_CONFLICT_CODE) || detail.includes('out of sync')
  }
  return false
}

async function fetchPackageDetail(packageId: number): Promise<PackageDetailResponse> {
  return apiRequestJson<PackageDetailResponse>(`${PACKAGES_BASE}/${packageId}`)
}

function packageHasReadyCorpus(documents: KnowledgeDocument[]): boolean {
  return documents.some((doc) => doc.status === 'completed')
}

async function ensurePackageReady(packageId: number): Promise<boolean> {
  const detail = await fetchPackageDetail(packageId)
  return packageHasReadyCorpus(detail.documents)
}

export function useMindMapDocumentSummary() {
  const { promptLanguage, t } = useLanguage()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()

  const isGenerating = ref(false)
  const isIndexingCorpus = ref(false)
  const isAdding = ref(false)

  async function applyMindMapResult(
    result: WebContentResult,
    options?: { successKey?: string }
  ): Promise<boolean> {
    if (!result.success || !result.spec) {
      const message = result.error || result.detail || t('canvas.mindMapDocumentSummary.generateFailed')
      notify.error(typeof message === 'string' ? message : t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    }

    await ensureFontsForLanguageCode(promptLanguage.value)
    const specToLoad = mergeMindMapPresentationExtrasIntoSpec(
      result.spec,
      diagramStore.data as Record<string, unknown> | null
    )
    const loaded = diagramStore.loadFromSpec(specToLoad, 'mindmap')
    if (!loaded) {
      notify.error(t('canvas.mindMapDocumentSummary.loadFailed'))
      return false
    }

    llmResultsStore.reset()
    notify.success(
      t(options?.successKey || 'canvas.mindMapDocumentSummary.generateSuccess')
    )
    return true
  }

  /**
   * Vision auto-detect: rebuild hand-drawn mind map onto canvas, or return false
   * when the image is a normal document photo (caller keeps OCR extract path).
   */
  async function rebuildFromImageFile(file: File): Promise<{
    applied: boolean
    isMindmap: boolean
  }> {
    isGenerating.value = true
    notify.showLoading(
      t('canvas.mindMapDocumentSummary.visionProgressDetecting', 'Detecting hand-drawn mind map…')
    )
    try {
      const uploadFile = await resizeImageFileForVisionUpload(file)
      const formData = new FormData()
      formData.append('file', uploadFile)
      formData.append('language', promptLanguage.value)
      const diagramId = savedDiagramsStore.activeDiagramId
      if (diagramId) {
        formData.append('diagram_id', diagramId)
      }

      const response = await apiUpload('/api/canvas/generate_mindmap_from_image', formData)
      const result = (await response.json().catch(() => ({}))) as WebContentResult
      if (!response.ok) {
        const detailMessage =
          typeof result.detail === 'string'
            ? result.detail
            : result.detail?.message
        notify.error(detailMessage || result.error || t('canvas.mindMapDocumentSummary.generateFailed'))
        return { applied: false, isMindmap: false }
      }

      if (result.is_mindmap && result.spec) {
        const applied = await applyMindMapResult(result, {
          successKey: 'canvas.mindMapDocumentSummary.visionRebuildSuccess',
        })
        return { applied, isMindmap: true }
      }

      return { applied: false, isMindmap: false }
    } catch (error) {
      console.error('[DocumentSummary] vision rebuild from image failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return { applied: false, isMindmap: false }
    } finally {
      notify.hideLoading()
      isGenerating.value = false
    }
  }

  /** Resize image sources before Document Summary package upload. */
  async function prepareImageUploadFile(file: File): Promise<File> {
    if (!isImageUploadFile(file)) {
      return file
    }
    return resizeImageFileForVisionUpload(file)
  }

  async function generateFromPackage(options: {
    packageId?: number | null
    diagramId?: string | null
    topicHint?: string
  }): Promise<boolean> {
    const packageId = options.packageId ?? undefined
    const diagramId = options.diagramId ?? savedDiagramsStore.activeDiagramId ?? undefined
    if (!packageId && !diagramId) {
      notify.warning(
        t(
          DOC_SUMMARY_LITE_UI
            ? 'canvas.mindMapDocumentSummary.generateNoCorpusLite'
            : 'canvas.mindMapDocumentSummary.generateNoCorpus'
        )
      )
      return false
    }

    isGenerating.value = true
    try {
      if (packageId && !DOC_SUMMARY_LITE_UI) {
        isIndexingCorpus.value = true
        const ready = await ensurePackageReady(packageId)
        isIndexingCorpus.value = false
        if (!ready) {
          notify.error(
            t(
              DOC_SUMMARY_LITE_UI
                ? 'canvas.mindMapDocumentSummary.generateNoCorpusLite'
                : 'canvas.mindMapDocumentSummary.generateNoCorpus'
            )
          )
          return false
        }
      }

      const response = await authFetch('/api/canvas/generate_mindmap_from_package', {
        method: 'POST',
        body: JSON.stringify({
          package_id: packageId,
          diagram_id: diagramId,
          topic_hint: options.topicHint,
          language: promptLanguage.value,
        }),
      })

      const result = (await response.json().catch(() => ({}))) as WebContentResult
      if (!response.ok) {
        if (isContentTooLongDetail(result.detail) || response.status === 413) {
          notify.error(t('canvas.mindMapDocumentSummary.contentTooLongForModel'))
          return false
        }
        if (isStorageConflictDetail(result.detail) || response.status === 409) {
          notify.error(t('canvas.mindMapDocumentSummary.storageConflictCleared'))
          if (packageId) {
            void queryClient.invalidateQueries({ queryKey: fileCenterKeys.package(packageId) })
          }
          void queryClient.invalidateQueries({ queryKey: fileCenterKeys.packages() })
          return false
        }
        const detailMessage =
          typeof result.detail === 'string'
            ? result.detail
            : result.detail?.message
        notify.error(detailMessage || result.error || t('canvas.mindMapDocumentSummary.generateFailed'))
        return false
      }

      return applyMindMapResult(result)
    } catch (error) {
      console.error('[DocumentSummary] generate from package failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    } finally {
      isIndexingCorpus.value = false
      isGenerating.value = false
    }
  }

  function validateUploadFile(file: File): boolean {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
    if (!ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
      notify.warning(
        t(
          DOC_SUMMARY_LITE_UI
            ? 'canvas.mindMapDocumentSummary.invalidFileType'
            : 'canvas.mindMapDocumentSummary.invalidDocType'
        )
      )
      return false
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      notify.warning(t('canvas.mindMapDocumentSummary.docTooLarge'))
      return false
    }
    return true
  }

  function isImageUploadFile(file: File): boolean {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
    return IMAGE_EXTENSIONS.has(ext) || file.type.startsWith('image/')
  }

  function extractStageLabel(stage: string | null | undefined): string {
    if (!stage) {
      return t('canvas.mindMapDocumentSummary.statusExtracting')
    }
    const key = EXTRACT_STAGE_I18N[stage]
    return key ? t(key) : t('canvas.mindMapDocumentSummary.statusExtracting')
  }

  /** @deprecated Use validateUploadFile — kept for non-lite panel paths. */
  function validateDocumentFile(file: File): boolean {
    return validateUploadFile(file)
  }

  return {
    isGenerating,
    isIndexingCorpus,
    isAdding,
    generateFromPackage,
    rebuildFromImageFile,
    prepareImageUploadFile,
    validateUploadFile,
    validateDocumentFile,
    isImageUploadFile,
    extractStageLabel,
    DOC_SUMMARY_UPLOAD_ACCEPT,
    MAX_CONTENT_LENGTH,
  }
}
