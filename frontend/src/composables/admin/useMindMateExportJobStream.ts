/**
 * SSE stream for MindMate export job progress (replaces HTTP polling).
 */
import { onUnmounted, ref, watch, type Ref } from 'vue'

import { useSSE } from '@/composables/core/useSSE'
import type { MindMateExportJob, MindMateExportJobStatus } from '@/composables/queries/adminApi'

const TERMINAL_JOB_STATUSES: MindMateExportJobStatus[] = [
  'completed',
  'completed_with_gaps',
  'cancelled',
  'failed',
  'failed_verification',
]

interface ExportJobStreamPayload {
  type?: string
  job?: MindMateExportJob
}

export function useMindMateExportJobStream(jobId: Ref<number | null>) {
  const job = ref<MindMateExportJob | null>(null)
  const { connect, close, isConnected } = useSSE()

  function handleMessage(data: unknown): void {
    const payload = data as ExportJobStreamPayload
    if (payload.type !== 'progress' || payload.job == null) {
      return
    }
    job.value = payload.job
    if (TERMINAL_JOB_STATUSES.includes(payload.job.status)) {
      close()
    }
  }

  watch(
    jobId,
    (id) => {
      close()
      job.value = null
      if (id == null) {
        return
      }
      connect(`/api/admin/mindmate-export/jobs/${id}/stream`, {
        onMessage: handleMessage,
        retryOnError: true,
        maxRetries: 5,
        retryDelay: 1500,
      })
    },
    { immediate: true }
  )

  onUnmounted(() => {
    close()
  })

  return {
    job,
    isConnected,
    close,
  }
}
