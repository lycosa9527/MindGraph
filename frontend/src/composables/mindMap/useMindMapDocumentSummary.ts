import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import type { PackageDetailResponse } from '@/composables/fileCenter/useFileCenter'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import { useDiagramStore, useLLMResultsStore, useSavedDiagramsStore } from '@/stores'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { authFetch } from '@/utils/api'
import { apiRequestJson } from '@/utils/apiClient'

const PACKAGES_BASE = '/api/knowledge-space/packages'

const MAX_CONTENT_LENGTH = 32000
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

/** File picker accept list for Document Summary lite uploads. */
export const DOC_SUMMARY_UPLOAD_ACCEPT =
  '.pdf,.docx,.pptx,.jpg,.jpeg,.png,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus,.amr,.wma,' +
  'application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,' +
  'application/vnd.openxmlformats-officedocument.presentationml.presentation,' +
  'image/jpeg,image/png,audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/flac,audio/ogg,audio/opus,audio/amr'

const ALLOWED_UPLOAD_EXTENSIONS = new Set([
  '.pdf',
  '.docx',
  '.pptx',
  '.jpg',
  '.jpeg',
  '.png',
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

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png'])

type WebContentResult = {
  success?: boolean
  spec?: Record<string, unknown>
  error?: string
  detail?: string
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
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()

  const isGenerating = ref(false)
  const isIndexingCorpus = ref(false)
  const isAdding = ref(false)

  async function applyMindMapResult(result: WebContentResult): Promise<boolean> {
    if (!result.success || !result.spec) {
      const message = result.error || result.detail || t('canvas.mindMapDocumentSummary.generateFailed')
      notify.error(message)
      return false
    }

    await ensureFontsForLanguageCode(promptLanguage.value)
    const loaded = diagramStore.loadFromSpec(result.spec, 'mindmap')
    if (!loaded) {
      notify.error(t('canvas.mindMapDocumentSummary.loadFailed'))
      return false
    }

    llmResultsStore.reset()
    notify.success(t('canvas.mindMapDocumentSummary.generateSuccess'))
    return true
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
        notify.error(result.detail || result.error || t('canvas.mindMapDocumentSummary.generateFailed'))
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

  /** @deprecated Use validateUploadFile — kept for non-lite panel paths. */
  function validateDocumentFile(file: File): boolean {
    return validateUploadFile(file)
  }

  return {
    isGenerating,
    isIndexingCorpus,
    isAdding,
    generateFromPackage,
    validateUploadFile,
    validateDocumentFile,
    isImageUploadFile,
    DOC_SUMMARY_UPLOAD_ACCEPT,
    MAX_CONTENT_LENGTH,
  }
}
