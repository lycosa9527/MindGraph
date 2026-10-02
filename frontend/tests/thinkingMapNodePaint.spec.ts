import { describe, expect, it } from 'vitest'

import { getMindMapThemeById } from '@/config/mindMapThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { DiagramNode } from '@/types'
import {
  restoreThinkingMapDefaultNodeColors,
  thinkingMapDisplayedNodeColors,
} from '@/utils/thinkingMapNodePaint'

function node(partial: DiagramNode): DiagramNode {
  return partial
}

describe('thinking map node paint', () => {
  it('paints a palette group with the solid theme and keeps a hand-painted color', () => {
    const palette = getMindmapBranchColor(1)
    const theme = getMindMapThemeById('vibrantOrange')
    const grouped = node({
      id: 'bubble-1',
      type: 'bubble',
      data: { groupIndex: 1 },
      style: { backgroundColor: palette.fill, borderColor: palette.border },
    })
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'vibrantOrange', grouped)).toEqual({
      backgroundColor: theme.backgroundColor,
      textColor: theme.textColor,
      borderColor: theme.borderColor,
    })
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'rainbow', grouped)).toBeNull()
    const painted = node({
      ...grouped,
      style: { backgroundColor: '#ff00aa', borderColor: '#ff00aa', textColor: '#111111' },
    })
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'vibrantOrange', painted)).toBeNull()
  })

  it('restores per-group colors on the default theme and clears the topic', () => {
    const palette = getMindmapBranchColor(0)
    const nodes = [
      node({
        id: 'topic',
        type: 'topic',
        style: {
          backgroundColor: '#111111',
          textColor: '#ffffff',
          borderColor: '#111111',
          fontSize: 18,
        },
      }),
      node({
        id: 'bubble-0',
        type: 'bubble',
        data: { groupIndex: 0 },
        style: { backgroundColor: '#111111', borderColor: '#111111', fontSize: 14 },
      }),
      node({
        id: 'sim',
        type: 'bubble',
        data: { groupIndex: 0, doubleBubbleRole: 'similarity' },
        style: { backgroundColor: '#111111', borderColor: '#111111' },
      }),
      node({
        id: 'diff',
        type: 'bubble',
        data: { groupIndex: 2, doubleBubbleRole: 'leftDiff' },
        style: { backgroundColor: '#111111', borderColor: '#111111' },
      }),
    ]
    restoreThinkingMapDefaultNodeColors('bubble_map', nodes.slice(0, 2))
    expect(nodes[0].style?.backgroundColor).toBeUndefined()
    expect(nodes[0].style?.fontSize).toBe(18)
    expect(nodes[1].style?.backgroundColor).toBe(palette.fill)
    expect(nodes[1].style?.borderColor).toBe(palette.border)
    expect(nodes[1].style?.fontSize).toBe(14)

    restoreThinkingMapDefaultNodeColors('double_bubble_map', nodes.slice(2))
    expect(nodes[2].style?.backgroundColor).toBeUndefined()
    const diffPalette = getMindmapBranchColor(2)
    expect(nodes[3].style?.backgroundColor).toBe(diffPalette.fill)
    expect(nodes[3].style?.borderColor).toBe(diffPalette.border)
  })
})
