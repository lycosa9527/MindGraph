import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import { useDiagramStore, useLLMResultsStore } from '@/stores'
import { authFetch } from '@/utils/api'

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

export function useMindMapDocumentSummary() {
  const { promptLanguage, t } = useLanguage()
  const notify = useNotifications()
  const diagramStore = useDiagramStore()
  const llmResultsStore = useLLMResultsStore()

  const isGenerating = ref(false)

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

  async function generateFromDocumentFile(file: File): Promise<boolean> {
    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
    if (!ALLOWED_DOC_EXTENSIONS.has(ext)) {
      notify.warning(t('canvas.mindMapDocumentSummary.invalidDocType'))
      return false
    }
    if (file.size > MAX_DOC_BYTES) {
      notify.warning(t('canvas.mindMapDocumentSummary.docTooLarge'))
      return false
    }

    isGenerating.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('language', promptLanguage.value)

      const response = await authFetch('/api/canvas/generate_mindmap_from_document_file', {
        method: 'POST',
        body: formData,
      })

      const result = (await response.json().catch(() => ({}))) as WebContentResult
      if (!response.ok) {
        notify.error(result.detail || result.error || t('canvas.mindMapDocumentSummary.generateFailed'))
        return false
      }

      return applyMindMapResult(result)
    } catch (error) {
      console.error('[DocumentSummary] generate from document file failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    } finally {
      isGenerating.value = false
    }
  }

  async function generateFromDocumentContent(
    pageContent: string,
    options?: { pageTitle?: string; contentFormat?: 'text/plain' | 'text/markdown' }
  ): Promise<boolean> {
    const trimmed = pageContent.trim()
    if (!trimmed) {
      notify.warning(t('canvas.mindMapDocumentSummary.emptyDocument'))
      return false
    }

    isGenerating.value = true
    try {
      const response = await authFetch('/api/canvas/generate_mindmap_from_document', {
        method: 'POST',
        body: JSON.stringify({
          page_content: trimmed.slice(0, MAX_CONTENT_LENGTH),
          content_format: options?.contentFormat ?? 'text/plain',
          page_title: options?.pageTitle,
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
      console.error('[DocumentSummary] generate from document failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    } finally {
      isGenerating.value = false
    }
  }

  async function generateFromWebUrl(pageUrl: string): Promise<boolean> {
    const url = pageUrl.trim()
    if (!url) {
      notify.warning(t('canvas.mindMapDocumentSummary.emptyUrl'))
      return false
    }

    isGenerating.value = true
    try {
      const response = await authFetch('/api/canvas/generate_mindmap_from_document', {
        method: 'POST',
        body: JSON.stringify({
          page_content: '',
          page_url: url,
          content_format: 'text/plain',
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
      console.error('[DocumentSummary] generate from URL failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    } finally {
      isGenerating.value = false
    }
  }

  async function generateFromImageFile(file: File): Promise<boolean> {
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      notify.warning(t('canvas.mindMapDocumentSummary.invalidImageType'))
      return false
    }

    isGenerating.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('language', promptLanguage.value)

      const response = await authFetch('/api/canvas/generate_mindmap_from_image', {
        method: 'POST',
        body: formData,
      })

      const result = (await response.json().catch(() => ({}))) as WebContentResult
      if (!response.ok) {
        notify.error(result.detail || result.error || t('canvas.mindMapDocumentSummary.generateFailed'))
        return false
      }

      return applyMindMapResult(result)
    } catch (error) {
      console.error('[DocumentSummary] generate from image failed:', error)
      notify.error(t('canvas.mindMapDocumentSummary.generateFailed'))
      return false
    } finally {
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
    generateFromDocumentContent,
    generateFromDocumentFile,
    generateFromWebUrl,
    generateFromImageFile,
    validateDocumentFile,
    ALLOWED_DOC_EXTENSIONS,
    ALLOWED_IMAGE_TYPES,
  }
}
