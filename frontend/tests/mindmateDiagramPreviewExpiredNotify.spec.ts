import { describe, expect, it, vi } from 'vitest'

import {
  notifyMindmateDiagramPreviewExpired,
  resetMindmateDiagramPreviewExpiredNotifies,
} from '@/utils/mindmateDiagramPreviewExpiredNotify'

describe('notifyMindmateDiagramPreviewExpired', () => {
  it('shows one toast per preview cache key per session', () => {
    resetMindmateDiagramPreviewExpiredNotifies()
    const showNotification = vi.fn()
    const onOpenCanvas = vi.fn()

    notifyMindmateDiagramPreviewExpired({
      cacheKey: 'dingtalk_deadbeef_1710000000.png',
      message: 'Preview expired',
      onOpenCanvas,
      notify: { showNotification },
    })
    notifyMindmateDiagramPreviewExpired({
      cacheKey: 'dingtalk_deadbeef_1710000000.png',
      message: 'Preview expired',
      onOpenCanvas,
      notify: { showNotification },
    })

    expect(showNotification).toHaveBeenCalledTimes(1)
    expect(showNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'warning',
        message: 'Preview expired',
        onClick: onOpenCanvas,
      })
    )
  })

  it('allows a second toast for a different preview key', () => {
    resetMindmateDiagramPreviewExpiredNotifies()
    const showNotification = vi.fn()

    notifyMindmateDiagramPreviewExpired({
      cacheKey: 'dingtalk_deadbeef_1710000000.png',
      message: 'A',
      onOpenCanvas: vi.fn(),
      notify: { showNotification },
    })
    notifyMindmateDiagramPreviewExpired({
      cacheKey: 'dingtalk_cafebabe_1710000001.png',
      message: 'B',
      onOpenCanvas: vi.fn(),
      notify: { showNotification },
    })

    expect(showNotification).toHaveBeenCalledTimes(2)
  })
})
