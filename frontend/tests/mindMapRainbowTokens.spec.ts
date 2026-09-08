import { describe, expect, it } from 'vitest'

import { getDefaultMindMapTheme, mindMapStyleFromTheme } from '@/config/mindMapThemes'
import {
  MIND_MAP_RAINBOW_FAMILIES,
  MIND_MAP_RAINBOW_THEME_ID,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
  mindMapRainbowNodeColors,
  rainbowAccentForL1Index,
} from '@/config/mindMapVibrantThemes'
import type { Connection } from '@/types'

describe('rainbow branch color tokens', () => {
  it('cycles six line/text/fill families', () => {
    expect(MIND_MAP_RAINBOW_FAMILIES).toHaveLength(6)
    expect(rainbowAccentForL1Index(0)).toBe('#2E90FA')
    expect(rainbowAccentForL1Index(6)).toBe('#2E90FA')
  })

  it('uses fill/text/line on L1 and a white left-bar treatment on L2', () => {
    const blue = MIND_MAP_RAINBOW_FAMILIES[0]
    const l1 = mindMapRainbowNodeColors(blue.line, 1)
    expect(l1).toEqual({
      backgroundColor: '#EBF3FE',
      textColor: '#175CD3',
      borderColor: '#2E90FA',
      borderWidth: 1.5,
      accentBarWidth: 0,
    })

    const l2 = mindMapRainbowNodeColors(blue.line, 2)
    expect(l2.backgroundColor).toBe('#FFFFFF')
    expect(l2.textColor).toBe('#175CD3')
    expect(l2.accentBarColor).toBe('#2E90FA')
    expect(l2.accentBarWidth).toBe(3)
    expect(l2.borderWidth).toBe(0)
  })

  it('keeps the central topic on brand blue', () => {
    expect(MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor).toBe('#3B5BDB')
    expect(MIND_MAP_RAINBOW_TOPIC_COLORS.topicTextColor).toBe('#ffffff')
  })

  it('is the default mind-map theme and paints L1 branches per family', () => {
    expect(getDefaultMindMapTheme().id).toBe(MIND_MAP_RAINBOW_THEME_ID)
    const connections: Connection[] = [
      { id: 'e1', source: 'topic', target: 'b1' },
      { id: 'e2', source: 'topic', target: 'b2' },
    ]
    const first = mindMapStyleFromTheme(
      { id: 'b1', type: 'branch' },
      getDefaultMindMapTheme(),
      'classic',
      connections
    )
    const second = mindMapStyleFromTheme(
      { id: 'b2', type: 'branch' },
      getDefaultMindMapTheme(),
      'classic',
      connections
    )
    expect(first.backgroundColor).toBe(MIND_MAP_RAINBOW_FAMILIES[0].fill)
    expect(second.backgroundColor).toBe(MIND_MAP_RAINBOW_FAMILIES[1].fill)
    expect(first.backgroundColor).not.toBe(second.backgroundColor)
  })
})
