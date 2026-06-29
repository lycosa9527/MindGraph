import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import type { PackageDetailResponse } from '@/composables/fileCenter/useFileCenter'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useDiagramStore, useLLMResultsStore, useSavedDiagramsStore } from '@/stores'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { authFetch } from '@/utils/api'
import { apiRequestJson } from '@/utils/apiClient'

const PACKAGES_BASE = '/api/knowledge-space/packages'
const PACKAGE_INDEX_POLL_MS = 2500
const PACKAGE_INDEX_TIMEOUT_MS = 10 * 60 * 1000

const MAX_CONTENT_LENGTH = 32000
const ALLOWED_DOC_EXTENSIONS = new Set(['.pdf', '.docx'])
const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/jpg'])
const MAX_DOC_BYTES = 20 * 1024 * 1024

type WebContentResult = {
  success?: boolean
  spec?: Record<string, unknown>
  error?: string
  detail?: string
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function packageNeedsIndexing(documents: KnowledgeDocument[]): boolean {
  return documents.some((doc) => doc.status === 'pending' || doc.status === 'processing')
}

function packageHasIndexedCorpus(documents: KnowledgeDocument[]): boolean {
  return documents.some((doc) => doc.status === 'completed')
}

async function fetchPackageDetail(packageId: number): Promise<PackageDetailResponse> {
  return apiRequestJson<PackageDetailResponse>(`${PACKAGES_BASE}/${packageId}`)
}

async function ensurePackageIndexed(packageId: number): Promise<boolean> {
  let detail = await fetchPackageDetail(packageId)
  const hasUnindexed = detail.documents.some(
    (doc) => doc.status === 'pending' || doc.status === 'failed'
  )
  if (hasUnindexed) {
    await apiRequestJson(`${PACKAGES_BASE}/${packageId}/documents/start-processing`, {
      method: 'POST',
    })
  }

  const deadline = Date.now() + PACKAGE_INDEX_TIMEOUT_MS
  while (Date.now() < deadline) {
    detail = await fetchPackageDetail(packageId)
    if (!packageNeedsIndexing(detail.documents)) {
      return packageHasIndexedCorpus(detail.documents)
    }
    await sleep(PACKAGE_INDEX_POLL_MS)
  }
  return false
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
      notify.warning(t('canvas.mindMapDocumentSummary.generateNoCorpus'))
      return false
    }

    isGenerating.value = true
    try {
      if (packageId) {
        isIndexingCorpus.value = true
        const indexed = await ensurePackageIndexed(packageId)
        isIndexingCorpus.value = false
        if (!indexed) {
          notify.error(t('canvas.mindMapDocumentSummary.generateNoCorpus'))
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

  function validateDocumentFile(file: File): boolean {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
    if (!ALLOWED_DOC_EXTENSIONS.has(ext)) {
      notify.warning(t('canvas.mindMapDocumentSummary.invalidDocType'))
      return false
    }
    if (file.size > MAX_DOC_BYTES) {
      notify.warning(t('canvas.mindMapDocumentSummary.docTooLarge'))
      return false
    }
    return true
  }

  return {
    isGenerating,
    isIndexingCorpus,
    isAdding,
    generateFromPackage,
    validateDocumentFile,
    ALLOWED_DOC_EXTENSIONS,
    ALLOWED_IMAGE_TYPES,
    MAX_CONTENT_LENGTH,
  }
}
