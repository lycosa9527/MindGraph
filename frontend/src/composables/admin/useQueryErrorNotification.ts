/**
 * Toast for Vue Query errors only while the owning scope is mounted; ignores cancel/abort.
 */
import { type Ref, watch } from 'vue'

import { useNotifications } from '@/composables'
import { httpErrorDetail } from '@/utils/httpErrorDetail'
import { isIgnorableQueryError } from '@/utils/queryErrors'

export function queryErrorMessage(err: unknown, fallback: string): string {
  if (isIgnorableQueryError(err)) {
    return ''
  }
  if (err instanceof Error && err.message.trim()) {
    return err.message
  }
  return httpErrorDetail({}) || fallback
}

export function shouldNotifyQueryError(err: unknown): boolean {
  return err != null && !isIgnorableQueryError(err)
}

export function useQueryErrorNotification(
  error: Ref<unknown>,
  getFallbackMessage: () => string
): void {
  const notify = useNotifications()

  watch(error, (err) => {
    if (!shouldNotifyQueryError(err)) {
      return
    }
    const message = queryErrorMessage(err, getFallbackMessage())
    if (message) {
      notify.error(message)
    }
  })
}
