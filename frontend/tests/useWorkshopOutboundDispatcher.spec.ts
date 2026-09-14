import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { useWorkshopOutboundDispatcher } from '@/composables/workshop/useWorkshopOutboundDispatcher'

describe('useWorkshopOutboundDispatcher sendUpdate', () => {
  it('does not enqueue diagram updates for viewers', () => {
    const enqueueUpdatePayload = vi.fn(() => 'op-1')
    const { sendUpdate } = useWorkshopOutboundDispatcher({
      ws: ref(null),
      diagramId: ref('diag-1'),
      pendingResync: ref(false),
      queueSize: ref(0),
      getSessionDiagramId: () => 'diag-1',
      canSendRealtimeControl: () => true,
      canEnqueueDiagramUpdate: () => false,
      clearRoomIdleCountdownUi: () => undefined,
      enqueueUpdatePayload,
    })

    expect(sendUpdate({ type: 'mindmap', nodes: [] })).toBeNull()
    expect(enqueueUpdatePayload).not.toHaveBeenCalled()
  })

  it('enqueues updates when the role may edit', () => {
    const enqueueUpdatePayload = vi.fn(() => 'op-1')
    const { sendUpdate } = useWorkshopOutboundDispatcher({
      ws: ref(null),
      diagramId: ref('diag-1'),
      pendingResync: ref(false),
      queueSize: ref(0),
      getSessionDiagramId: () => 'diag-1',
      canSendRealtimeControl: () => true,
      canEnqueueDiagramUpdate: () => true,
      clearRoomIdleCountdownUi: () => undefined,
      enqueueUpdatePayload,
    })

    expect(sendUpdate({ type: 'mindmap', nodes: [] })).toBe('op-1')
    expect(enqueueUpdatePayload).toHaveBeenCalledOnce()
  })
})
