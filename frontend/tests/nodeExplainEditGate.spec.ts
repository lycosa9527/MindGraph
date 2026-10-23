import { beforeEach, describe, expect, it } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  ensureNodeExplainEditGate,
  isNodeExplainLocked,
  openNodeExplainEditIds,
  setNodeExplainOutlineEditing,
} from '@/composables/mindMap/nodeExplainEditGate'
import { isNodeExplainTriggerTarget } from '@/utils/nodeExplainTrigger'

describe('nodeExplainEditGate', () => {
  beforeEach(() => {
    ensureNodeExplainEditGate()
    setNodeExplainOutlineEditing(null)
    for (const nodeId of [...openNodeExplainEditIds()]) {
      eventBus.emit('node_editor:closed', { nodeId })
    }
  })

  it('locks node explain while an inline editor is open', () => {
    expect(isNodeExplainLocked()).toBe(false)
    eventBus.emit('node_editor:opening', { nodeId: 'branch-1' })
    expect(isNodeExplainLocked()).toBe(true)
    eventBus.emit('node_editor:closed', { nodeId: 'branch-1' })
    expect(isNodeExplainLocked()).toBe(false)
  })

  it('locks while the outline editor is open', () => {
    setNodeExplainOutlineEditing('branch-1')
    expect(isNodeExplainLocked()).toBe(true)
    setNodeExplainOutlineEditing(null)
    expect(isNodeExplainLocked()).toBe(false)
  })

  it('locks while the mind-map edit session is still open', () => {
    expect(isNodeExplainLocked({ editingNodeId: 'branch-1' })).toBe(true)
    expect(isNodeExplainLocked({ pendingEditNodeId: 'branch-2' })).toBe(true)
  })

  it('recognizes the node-explain control as a trigger', () => {
    const button = document.createElement('button')
    button.setAttribute('data-node-explain-trigger', '')
    const icon = document.createElement('span')
    button.appendChild(icon)
    expect(isNodeExplainTriggerTarget(icon)).toBe(true)
    expect(isNodeExplainTriggerTarget(document.createElement('div'))).toBe(false)
  })
})
