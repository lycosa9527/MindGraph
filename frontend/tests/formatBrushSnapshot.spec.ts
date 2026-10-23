import { describe, expect, it } from 'vitest'

import {
  resolveFormatBrushThemeFallback,
  snapshotFormatBrushStyleForNode,
} from '@/composables/canvasToolbar/formatBrushSnapshot'
import type { DiagramNode } from '@/types'

describe('formatBrushSnapshot', () => {
  it('resolves concept-map theme paint when the store has no inline style', () => {
    const topic: DiagramNode = {
      id: 'topic',
      type: 'topic',
      text: 'Focus',
      position: { x: 0, y: 0 },
    }
    const fallback = resolveFormatBrushThemeFallback('concept_map', { _mindmap_theme: 'vibrantBlue' }, topic)
    expect(fallback?.backgroundColor).toBeTruthy()
    expect(fallback?.textColor).toBeTruthy()
    expect(fallback?.borderColor).toBeTruthy()
  })

  it('snapshots mind-map theme defaults for an unstyled branch', () => {
    const branch: DiagramNode = {
      id: 'branch-1',
      type: 'branch',
      text: 'Idea',
      position: { x: 0, y: 0 },
    }
    const copied = snapshotFormatBrushStyleForNode({
      diagramType: 'mindmap',
      data: { nodes: [branch], connections: [] },
      sourceNode: branch,
      persistedStyle: undefined,
    })
    expect(copied.backgroundColor).toBeTruthy()
    expect(copied.fontSize).toBeTruthy()
  })
})
