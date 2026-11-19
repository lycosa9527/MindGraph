/**
 * Mint the glasses sheet QR when the learning-sheet toggle turns on.
 */
import { type Ref, computed, reactive, ref } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'
import { useDiagramStore } from '@/stores/diagram'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { apiRequest } from '@/utils/apiClient'

type MintedSheet = {
  qr_payload?: string
}

export function useWorksheetSheetQr(
  draft: Ref<CanvasWorksheetTextOptions>,
  defaultTopic: () => string
) {
  const notify = useNotifications()
  const diagramStore = useDiagramStore()
  const savedDiagrams = useSavedDiagramsStore()
  const busy = ref(false)

  const src = computed(() => {
    const numbered = draft.value.classPersonalize ? draft.value.sheetCopyPayloads[0] || '' : ''
    const payload = (numbered || draft.value.sheetQrPayload).trim()
    if (!draft.value.showSheetQr || !payload) {
      return ''
    }
    return `/api/qrcode?data=${encodeURIComponent(payload)}&size=216`
  })

  async function ensure(): Promise<boolean> {
    if (draft.value.showSheetQr && draft.value.sheetQrPayload.trim()) {
      return true
    }
    await toggle()
    return Boolean(draft.value.showSheetQr && draft.value.sheetQrPayload.trim())
  }

  async function toggle() {
    if (draft.value.showSheetQr) {
      draft.value.showSheetQr = false
      return
    }
    busy.value = true
    try {
      const spec = diagramStore.getSpecForSave() ?? { topic: defaultTopic() }
      const response = await apiRequest('/api/learning-space/glasses/sheets', {
        method: 'POST',
        body: JSON.stringify({
          diagram_id: savedDiagrams.activeDiagramId || '',
          spec,
        }),
      })
      if (!response.ok) {
        notify.errorKey('canvas.worksheetText.sheetQrFailed')
        return
      }
      const body = (await response.json()) as MintedSheet
      const payload = (body.qr_payload || '').trim()
      if (!payload) {
        notify.errorKey('canvas.worksheetText.sheetQrFailed')
        return
      }
      draft.value.sheetQrPayload = payload
      draft.value.showSheetQr = true
    } catch {
      notify.errorKey('canvas.worksheetText.sheetQrFailed')
    } finally {
      busy.value = false
    }
  }

  return reactive({ busy, src, toggle, ensure })
}
