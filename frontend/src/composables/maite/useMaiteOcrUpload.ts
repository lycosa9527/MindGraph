/**
 * Maite OCR upload handler — listens for ocr_requested and emits ocr_completed.
 */
import { onScopeDispose, ref } from 'vue'

import { ocrProblem } from '@/api/maite/problems'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

export function useMaiteOcrUpload() {
  const store = useMaiteStore()
  const uploading = ref(false)
  const errorMessage = ref('')

  async function handleOcr(file: File, scene: 'demo' | 'question'): Promise<void> {
    uploading.value = true
    errorMessage.value = ''
    try {
      const result = await ocrProblem(file)
      const text = result.clean_text || result.raw_text
      store.setCurrentProblemText(text)
      eventBus.emit('maite:ocr_completed', {
        text,
        imageUrl: result.stored_path ?? undefined,
        scene,
      })
      eventBus.emit('maite:problem_ready', {
        problemId: 0,
        text,
        imageUrl: result.stored_path ?? undefined,
      })
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
