/**
 * Save-status chip for the mobile shell header (right of the page title).
 * The canvas page publishes it; MobileLayout only reads it.
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

export type MobileCanvasSaveStatusTone = 'saving' | 'dirty' | 'saved'

export interface MobileCanvasSaveStatus {
  text: string
  tone: MobileCanvasSaveStatusTone
}

const mobileCanvasSaveStatus = ref<MobileCanvasSaveStatus | null>(null)

export function useMobileCanvasSaveStatus(): Ref<MobileCanvasSaveStatus | null> {
  return mobileCanvasSaveStatus
}

export function publishMobileCanvasHeaderSaveStatus(source: {
  text: ComputedRef<string | null>
  isSaving: Ref<boolean>
  isDirty: Ref<boolean>
}): void {
  function sync(): void {
    const text = source.text.value
    if (!text) {
      mobileCanvasSaveStatus.value = null
      return
    }
    let tone: MobileCanvasSaveStatusTone = 'saved'
    if (source.isSaving.value) {
      tone = 'saving'
    } else if (source.isDirty.value) {
      tone = 'dirty'
    }
    mobileCanvasSaveStatus.value = { text, tone }
  }

  watch([source.text, source.isSaving, source.isDirty], sync, { immediate: true })

  onUnmounted(() => {
    mobileCanvasSaveStatus.value = null
  })
}
