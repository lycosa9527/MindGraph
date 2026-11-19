/**
 * Number a class roster onto one learning sheet, one QR sequence per student.
 */
import { type Ref, reactive, ref } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'
import { apiRequest } from '@/utils/apiClient'

type TeacherClass = {
  id: number
  name: string
}

type CopyRow = {
  qr_payload?: string
}

export function useWorksheetClassCopies(
  draft: Ref<CanvasWorksheetTextOptions>,
  ensureQr: () => Promise<boolean>
) {
  const notify = useNotifications()
  const busy = ref(false)
  const classes = ref<TeacherClass[]>([])

  async function loadClasses(): Promise<TeacherClass[]> {
    const response = await apiRequest('/api/learning-space/teacher/classes')
    if (!response.ok) return []
    const body = (await response.json()) as { items?: TeacherClass[] }
    return (body.items || []).filter((item) => item && item.id > 0)
  }

  async function assign(classId: number): Promise<boolean> {
    const response = await apiRequest('/api/learning-space/glasses/sheets/copies', {
      method: 'POST',
      body: JSON.stringify({
        qr_payload: draft.value.sheetQrPayload,
        class_id: classId,
      }),
    })
    if (!response.ok) {
      notify.errorKey(
        response.status === 400
          ? 'canvas.worksheetText.classPersonalEmpty'
          : 'canvas.worksheetText.classPersonalFailed'
      )
      return false
    }
    const body = (await response.json()) as { copies?: CopyRow[] }
    const payloads = (body.copies || [])
      .map((row) => (row.qr_payload || '').trim())
      .filter((payload) => payload.length > 0)
    if (payloads.length === 0) {
      notify.errorKey('canvas.worksheetText.classPersonalEmpty')
      return false
    }
    draft.value.classId = classId
    draft.value.sheetCopyPayloads = payloads
    draft.value.classPersonalize = true
    return true
  }

  async function toggle() {
    if (draft.value.classPersonalize) {
      draft.value.classPersonalize = false
      draft.value.sheetCopyPayloads = []
      return
    }
    busy.value = true
    try {
      const ready = await ensureQr()
      if (!ready) return
      classes.value = await loadClasses()
      const classId = draft.value.classId || classes.value[0]?.id || 0
      if (!classId) {
        notify.errorKey('canvas.worksheetText.classPersonalNone')
        return
      }
      await assign(classId)
    } catch {
      notify.errorKey('canvas.worksheetText.classPersonalFailed')
    } finally {
      busy.value = false
    }
  }

  async function select(classId: number) {
    if (!classId || classId === draft.value.classId) return
    busy.value = true
    try {
      const ready = await ensureQr()
      if (!ready) return
      await assign(classId)
    } catch {
      notify.errorKey('canvas.worksheetText.classPersonalFailed')
    } finally {
      busy.value = false
    }
  }

  return reactive({ busy, classes, toggle, select })
}
