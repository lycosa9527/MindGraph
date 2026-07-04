/** Session-scoped toast when a MindMate diagram preview cannot be resolved locally. */

import type { useNotifications } from '@/composables/core/useNotifications'

type NotifyApi = Pick<ReturnType<typeof useNotifications>, 'showNotification'>

const notifiedPreviewKeys = new Set<string>()

export interface MindmateDiagramPreviewExpiredNotifyOptions {
  cacheKey: string
  message: string
  onOpenCanvas: () => void
  notify: NotifyApi
}

/** Show at most one warning toast per preview filename per browser session. */
export function notifyMindmateDiagramPreviewExpired(
  options: MindmateDiagramPreviewExpiredNotifyOptions
): void {
  const cacheKey = options.cacheKey.trim().toLowerCase()
  if (!cacheKey || notifiedPreviewKeys.has(cacheKey)) {
    return
  }
  notifiedPreviewKeys.add(cacheKey)
  options.notify.showNotification({
    type: 'warning',
    message: options.message,
    duration: 8000,
    onClick: options.onOpenCanvas,
  })
}

export function resetMindmateDiagramPreviewExpiredNotifies(): void {
  notifiedPreviewKeys.clear()
}
