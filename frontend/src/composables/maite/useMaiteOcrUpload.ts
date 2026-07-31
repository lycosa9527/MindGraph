/**
 * Maite OCR upload handler — listens for ocr_requested and emits ocr_completed.
 * Persists a practice conversation as soon as OCR text is ready.
 */
import { onScopeDispose, ref } from 'vue'

import { ocrProblem } from '@/api/maite/problems'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'
import { persistMaitePractice } from '@/composables/maite/useMaitePracticePersist'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteMode } from '@/types/maite'

export function useMaiteOcrUpload() {
  const store = useMaiteStore()
  const { t } = useLanguage()
  const uploading = ref(false)
  const errorMessage = ref('')

  async function handleOcr(file: File, scene: 'demo' | 'question'): Promise<void> {
    uploading.value = true
    errorMessage.value = ''
    notify.info(t('maite.toast.ocr_uploading'))
    try {
      const result = await ocrProblem(file)
      const text = (result.clean_text || result.raw_text).trim()
      if (!text) {
        throw new Error('ocr_failed')
      }
      store.setCurrentProblemText(text)
      const imageUrl = result.stored_path ?? undefined
      const mode: MaiteMode = scene === 'question' ? 'inquiry' : 'demo'

      // Save conversation immediately (MindMate-style), before decompose/inquiry.
      try {
        await persistMaitePractice({ text, imageUrl, mode })
        notify.success(t('maite.toast.practice_saved'))
      } catch (persistError: unknown) {
        eventBus.emit('maite:error', {
          message: persistError instanceof Error ? persistError.message : 'create_failed',
          source: 'ocr_practice_persist',
        })
      }

      eventBus.emit('maite:ocr_completed', {
        text,
        imageUrl,
        scene,
      })
      notify.success(t('maite.toast.ocr_success'))
    } catch (error: unknown) {
      errorMessage.value = error instanceof Error ? error.message : 'ocr_failed'
      eventBus.emit('maite:error', {
        message: errorMessage.value,
        source: 'ocr_upload',
      })
    } finally {
      uploading.value = false
    }
  }

  const offRequested = eventBus.on('maite:ocr_requested', ({ file, scene }) => {
    void handleOcr(file, scene)
  })

  onScopeDispose(() => {
    offRequested()
  })

  return {
    uploading,
    errorMessage,
    handleOcr,
  }
}
