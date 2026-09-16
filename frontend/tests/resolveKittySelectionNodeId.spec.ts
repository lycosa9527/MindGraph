/**
 * resolveKittySelectionNodeId — voice underscore ids vs Vue Flow ids.
 */
import { describe, expect, it } from 'vitest'

import { resolveKittySelectionNodeId } from '@/composables/kitty/kittyDiagramChildren'

describe('resolveKittySelectionNodeId', () => {
  const leftoverCircleNodes = [
    { id: 'context-0', type: 'context', text: 'Wheels' },
    { id: 'context-1', type: 'context', text: 'Engine' },
  ]
  const migratedCircleNodes = [
    {
      id: 'uid-context-a',
      type: 'bubble',
      text: 'Wheels',
      data: { groupIndex: 0, circleMapLegacyId: 'context-0' },
    },
    {
      id: 'uid-context-b',
      type: 'bubble',
      text: 'Engine',
      data: { groupIndex: 1, circleMapLegacyId: 'context-1' },
    },
  ]

  it('treats leftover context-0 as a hint that resolves after migrate', () => {
    const id = resolveKittySelectionNodeId('circle_map', migratedCircleNodes, {
      nodeId: 'context-0',
    })
    expect(id).toBe('uid-context-a')
  })

  it('maps context_0 leftover hint to the live UUID', () => {
    const id = resolveKittySelectionNodeId('circle_map', migratedCircleNodes, {
      nodeId: 'context_0',
    })
    expect(id).toBe('uid-context-a')
  })

  it('still accepts leftover slot ids as hints on unmigrated nodes', () => {
    const id = resolveKittySelectionNodeId('circle_map', leftoverCircleNodes, {
      nodeId: 'context_0',
    })
    expect(id).toBe('context-0')
  })

  it('passes through existing Vue Flow id', () => {
    const id = resolveKittySelectionNodeId('circle_map', migratedCircleNodes, {
      nodeId: 'uid-context-b',
    })
    expect(id).toBe('uid-context-b')
  })

  it('resolves by child index when nodeId missing', () => {
    const id = resolveKittySelectionNodeId('circle_map', leftoverCircleNodes, {
      nodeIndex: 1,
    })
    expect(id).toBe('context-1')
  })
})
