/**
 * resolveKittySelectionNodeId — voice underscore ids vs Vue Flow ids.
 */
import { describe, expect, it } from 'vitest'

import { resolveKittySelectionNodeId } from '@/composables/kitty/kittyDiagramChildren'

describe('resolveKittySelectionNodeId', () => {
  const circleNodes = [
    { id: 'context-0', type: 'context', text: 'Wheels' },
    { id: 'context-1', type: 'context', text: 'Engine' },
  ]

  it('maps context_0 to context-0 for circle_map', () => {
    const id = resolveKittySelectionNodeId('circle_map', circleNodes, {
      nodeId: 'context_0',
    })
    expect(id).toBe('context-0')
  })

  it('passes through existing Vue Flow id', () => {
    const id = resolveKittySelectionNodeId('circle_map', circleNodes, {
      nodeId: 'context-1',
    })
    expect(id).toBe('context-1')
  })

  it('resolves by child index when nodeId missing', () => {
    const id = resolveKittySelectionNodeId('circle_map', circleNodes, {
      nodeIndex: 1,
    })
    expect(id).toBe('context-1')
  })
})
