import { describe, expect, it } from 'vitest'

import { getMindMapThemeById } from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_FAMILIES } from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { DiagramNode } from '@/types'
import { thinkingMapBorderWidth } from '@/utils/thinkingMapChrome'
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
    const family = MIND_MAP_RAINBOW_FAMILIES[1]
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'rainbow', grouped)).toMatchObject({
      backgroundColor: family.fill,
      textColor: family.text,
      borderColor: family.line,
    })
    const painted = node({
      ...grouped,
      style: { backgroundColor: '#ff00aa', borderColor: '#ff00aa', textColor: '#111111' },
    })
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'vibrantOrange', painted)).toBeNull()
  })

  it('restores per-group colors on the default theme and clears the topic', () => {
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
    const restored = MIND_MAP_RAINBOW_FAMILIES[0]
    expect(nodes[1].style?.backgroundColor).toBe(restored.fill)
    expect(nodes[1].style?.borderColor).toBe(restored.line)
    expect(nodes[1].style?.fontSize).toBe(14)

    restoreThinkingMapDefaultNodeColors('double_bubble_map', nodes.slice(2))
    expect(nodes[2].style?.backgroundColor).toBe('#FFFFFF')
    expect(nodes[2].style?.borderColor).toBe('#3B5BDB')
    const diffFamily = MIND_MAP_RAINBOW_FAMILIES[2]
    expect(nodes[3].style?.backgroundColor).toBe(diffFamily.fill)
    expect(nodes[3].style?.borderColor).toBe(diffFamily.line)
  })

  it('keeps a painted zero border and ignores a leftover stored zero', () => {
    expect(thinkingMapBorderWidth(0, 1.5, 1.5)).toBe(0)
    expect(thinkingMapBorderWidth(undefined, 0, 1.5)).toBe(1.5)
    expect(thinkingMapBorderWidth(undefined, 2, 1.5)).toBe(2)
  })
})
