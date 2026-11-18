import { describe, expect, it } from 'vitest'

import { getMindMapThemeById } from '@/config/mindMapThemes'
import {
  MIND_MAP_RAINBOW_FAMILIES,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
} from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { DiagramNode } from '@/types'
import { thinkingMapBorderWidth } from '@/utils/thinkingMapChrome'
import {
  doubleBubbleConnectorStroke,
  restoreThinkingMapDefaultNodeColors,
  syncDoubleBubbleConnectionsToLeafBorders,
  thinkingMapDisplayedNodeColors,
  thinkingMapRenderedConnectorStroke,
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
    const stampedText = node({
      ...grouped,
      style: {
        backgroundColor: palette.fill,
        borderColor: palette.border,
        textColor: MIND_MAP_RAINBOW_FAMILIES[1].text,
      },
    })
    expect(
      thinkingMapDisplayedNodeColors('bubble_map', 'vibrantOrange', stampedText)
    ).toMatchObject({
      backgroundColor: theme.backgroundColor,
      borderColor: theme.borderColor,
    })
  })

  it('paints a default similarity with the solid theme', () => {
    const theme = getMindMapThemeById('vibrantYellow')
    const sim = node({
      id: 'sim',
      type: 'bubble',
      data: { doubleBubbleRole: 'similarity' },
      style: { backgroundColor: '#FFFFFF', borderColor: '#3B5BDB', textColor: '#334155' },
    })
    expect(thinkingMapDisplayedNodeColors('double_bubble_map', 'vibrantYellow', sim)).toEqual({
      backgroundColor: theme.backgroundColor,
      textColor: theme.textColor,
      borderColor: theme.borderColor,
    })
    const applied = node({
      id: 'bubble-2',
      type: 'bubble',
      data: { groupIndex: 2 },
      style: {
        backgroundColor: theme.backgroundColor,
        textColor: theme.textColor,
        borderColor: theme.borderColor,
      },
    })
    expect(thinkingMapDisplayedNodeColors('bubble_map', 'vibrantYellow', applied)).toBeNull()
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

  it('keeps a white role fill when only the text color changes', () => {
    const customText = '#dc2626'
    const similarity = node({
      id: 'sim-1',
      type: 'bubble',
      data: { doubleBubbleRole: 'similarity' },
      style: { textColor: customText },
    })
    const similarityPaint = thinkingMapDisplayedNodeColors(
      'double_bubble_map',
      'rainbow',
      similarity
    )
    expect(similarityPaint?.backgroundColor).toBe('#FFFFFF')
    expect(similarityPaint?.borderColor).toBe('#3B5BDB')
    expect(similarityPaint?.textColor).toBeUndefined()

    const leaf = node({
      id: 'leaf-1',
      type: 'branch',
      data: { nodeType: 'leaf', categoryIndex: 1 },
      style: { textColor: customText },
    })
    const leafPaint = thinkingMapDisplayedNodeColors('tree_map', 'rainbow', leaf)
    const green = MIND_MAP_RAINBOW_FAMILIES[1]
    expect(leafPaint?.backgroundColor).toBe('#FFFFFF')
    expect(leafPaint?.accentBarColor).toBe(green.line)
    expect(leafPaint?.textColor).toBeUndefined()

    const palette = getMindmapBranchColor(1)
    const grouped = node({
      id: 'bubble-1',
      type: 'bubble',
      data: { groupIndex: 1 },
      style: {
        backgroundColor: palette.fill,
        borderColor: palette.border,
        textColor: customText,
      },
    })
    const groupedPaint = thinkingMapDisplayedNodeColors('bubble_map', 'rainbow', grouped)
    expect(groupedPaint?.backgroundColor).toBe(green.fill)
    expect(groupedPaint?.textColor).toBeUndefined()

    const theme = getMindMapThemeById('vibrantYellow')
    const themedSimilarity = thinkingMapDisplayedNodeColors(
      'double_bubble_map',
      'vibrantYellow',
      similarity
    )
    expect(themedSimilarity?.backgroundColor).toBe(theme.backgroundColor)
    expect(themedSimilarity?.textColor).toBeUndefined()
  })

  it('keeps the topic stroke until a hand-painted fill would hide it', () => {
    const similarity = node({
      id: 'sim-1',
      type: 'bubble',
      text: 'Red when ripe',
      data: { doubleBubbleRole: 'similarity' },
    })
    const topic = node({
      id: 'left-topic',
      type: 'topic',
      text: 'Tomato',
    })
    expect(
      thinkingMapRenderedConnectorStroke(
        'double_bubble_map',
        'rainbow',
        undefined,
        topic,
        similarity
      )
    ).toBe(MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor)

    const blue = node({
      ...similarity,
      style: { backgroundColor: 'rgba(11,181,236,1)' },
    })
    expect(
      thinkingMapRenderedConnectorStroke('double_bubble_map', 'rainbow', undefined, topic, blue)
    ).toBe('#1e293b')

    const red = node({
      ...similarity,
      style: { backgroundColor: '#F04438' },
    })
    expect(
      thinkingMapRenderedConnectorStroke('double_bubble_map', 'rainbow', '#2E90FA', topic, red)
    ).toBe('#2E90FA')
    const sameLine = node({
      ...similarity,
      style: { backgroundColor: '#2E90FA' },
    })
    expect(
      thinkingMapRenderedConnectorStroke('double_bubble_map', 'rainbow', '#2E90FA', topic, sameLine)
    ).toBe('#1e293b')
  })

  it('keeps a painted zero border and ignores a leftover stored zero', () => {
    expect(thinkingMapBorderWidth(0, 1.5, 1.5)).toBe(0)
    expect(thinkingMapBorderWidth(undefined, 0, 1.5)).toBe(1.5)
    expect(thinkingMapBorderWidth(undefined, 2, 1.5)).toBe(2)
    // Explicit user width beats solid theme chrome (paint width still present).
    expect(thinkingMapBorderWidth(1.5, 3, 1.5)).toBe(3)
  })

  it('follows similarity and difference border colors for double-bubble connectors', () => {
    const topic = node({ id: 'left-topic', type: 'topic', text: 'A' })
    const similarity = node({
      id: 'sim-1',
      type: 'bubble',
      data: { doubleBubbleRole: 'similarity' },
      style: { borderColor: '#aa00aa' },
    })
    expect(doubleBubbleConnectorStroke('rainbow', '#2E90FA', topic, similarity)).toBe('#aa00aa')

    const leftDiff = node({
      id: 'ld-1',
      type: 'bubble',
      data: { doubleBubbleRole: 'leftDiff', groupIndex: 0 },
      style: { backgroundColor: '#FEE4E2', borderColor: '#F04438' },
    })
    expect(doubleBubbleConnectorStroke('rainbow', '#2E90FA', topic, leftDiff)).toBe('#F04438')

    // Topic border alone does not drive the stroke when the leaf still has chrome/default paint.
    const plainSim = node({
      id: 'sim-2',
      type: 'bubble',
      data: { doubleBubbleRole: 'similarity' },
    })
    const paintedTopic = node({
      id: 'left-topic',
      type: 'topic',
      style: { borderColor: '#00ff00' },
    })
    expect(doubleBubbleConnectorStroke('rainbow', undefined, paintedTopic, plainSim)).toBe(
      MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    )
  })

  it('syncs only leaf-touching edges when a difference border is painted', () => {
    const connections = [
      {
        id: 'edge-left-topic-ld-1',
        source: 'left-topic',
        target: 'ld-1',
        style: { strokeColor: '#111111' },
      },
      {
        id: 'edge-left-topic-sim-1',
        source: 'left-topic',
        target: 'sim-1',
        style: { strokeColor: '#222222' },
      },
    ]
    const nodes = [
      node({ id: 'left-topic', type: 'topic' }),
      node({
        id: 'ld-1',
        type: 'bubble',
        data: { doubleBubbleRole: 'leftDiff', groupIndex: 0 },
      }),
      node({
        id: 'sim-1',
        type: 'bubble',
        data: { doubleBubbleRole: 'similarity' },
      }),
    ]
    syncDoubleBubbleConnectionsToLeafBorders(connections, nodes, ['ld-1', 'left-topic'], '#F04438')
    expect(connections[0]?.style?.strokeColor).toBe('#F04438')
    expect(connections[1]?.style?.strokeColor).toBe('#222222')
  })
})
