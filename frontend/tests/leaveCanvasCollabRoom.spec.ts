import { afterEach, describe, expect, it, vi } from 'vitest'

import { leaveCanvasCollabRoom } from '@/composables/canvasPage/leaveCanvasCollabRoom'
import { eventBus } from '@/composables/core/useEventBus'
import {
  persistWorkshopSession,
  readWorkshopSession,
} from '@/utils/workshopSessionStorage'

afterEach(() => {
  sessionStorage.clear()
})

describe('leaveCanvasCollabRoom', () => {
  it('clears restore keys and broadcasts a null room', () => {
    persistWorkshopSession('ABC-DEF', 'diag-1')
    const onCodeChanged = vi.fn()
    eventBus.on('workshop:code-changed', onCodeChanged)

    leaveCanvasCollabRoom()

    expect(readWorkshopSession()).toBeNull()
    expect(onCodeChanged).toHaveBeenCalledWith({ code: null, visibility: null })
    eventBus.off('workshop:code-changed', onCodeChanged)
  })
})
