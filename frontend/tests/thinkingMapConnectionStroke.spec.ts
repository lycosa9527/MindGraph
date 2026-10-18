import { describe, expect, it } from 'vitest'

import { getMindMapThemeById } from '@/config/mindMapThemes'
import {
  MIND_MAP_RAINBOW_FAMILIES,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
} from '@/config/mindMapVibrantThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  connectorStrokeReadableOnFills,
  resolveThinkingMapConnectorStroke,
  thinkingMapAdaptiveTextColor,
  thinkingMapAdaptiveTopicTextColor,
  thinkingMapSolidThemeStroke,
  thinkingMapStructureColor,
} from '@/utils/thinkingMapConnectionStroke'

describe('thinking map connection stroke', () => {
  it('maps a Material border onto the rainbow family line', () => {
    const palette = getMindmapBranchColor(2).border
    const familyLine = MIND_MAP_RAINBOW_FAMILIES[2].line
    expect(thinkingMapSolidThemeStroke(undefined)).toBeNull()
    expect(thinkingMapSolidThemeStroke(null)).toBeNull()
    expect(thinkingMapSolidThemeStroke('rainbow')).toBeNull()
    expect(resolveThinkingMapConnectorStroke('rainbow', palette, '#666')).toBe(familyLine)
    expect(resolveThinkingMapConnectorStroke(undefined, undefined, '#666')).toBe(
      MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    )
  })

  it('paints every connector with the solid theme accent', () => {
    const accent = getMindMapThemeById('vibrantOrange').borderColor
    const palette = getMindmapBranchColor(0).border
    expect(thinkingMapSolidThemeStroke('vibrantOrange')).toBe(accent)
    expect(accent).not.toBe(palette)
    expect(resolveThinkingMapConnectorStroke('vibrantOrange', palette, '#94a3b8')).toBe(accent)
    expect(resolveThinkingMapConnectorStroke('vibrantOrange', undefined, '#94a3b8')).toBe(accent)
  })

  it('paints rings and dimension labels with the solid theme topic stroke', () => {
    const stroke = getMindMapThemeById('vibrantYellow').topicBorderColor
    expect(thinkingMapStructureColor('vibrantYellow')).toBe(stroke)
    expect(stroke).not.toBe(getMindMapThemeById('vibrantYellow').borderColor)
    expect(thinkingMapStructureColor('rainbow')).toBe(
      MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    )
    expect(thinkingMapStructureColor(undefined)).toBe(
      MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    )
    const theme = getMindMapThemeById('vibrantYellow')
    const obsidian = getMindMapThemeById('obsidianDark')
    expect(thinkingMapAdaptiveTextColor('vibrantYellow', '#3B5BDB')).toBe(theme.textColor)
    expect(thinkingMapAdaptiveTextColor('obsidianDark', '#3B5BDB')).toBe(obsidian.topicBorderColor)
    expect(thinkingMapAdaptiveTextColor('rainbow', '#3B5BDB')).toBe('#3B5BDB')
    expect(thinkingMapAdaptiveTopicTextColor('vibrantYellow', '#ffffff')).toBe('#ffffff')
    expect(thinkingMapAdaptiveTopicTextColor('vibrantBlue', '#ffffff')).toBe('#ffffff')
    expect(thinkingMapAdaptiveTopicTextColor(undefined, '#ffffff')).toBe('#ffffff')
  })

  it('darkens a connector only when the fill is the same hue', () => {
    const topicBlue = MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
    expect(connectorStrokeReadableOnFills(topicBlue, ['#FFFFFF', undefined])).toBe(topicBlue)
    expect(connectorStrokeReadableOnFills(topicBlue, ['#EBF3FE'])).toBe(topicBlue)
    expect(connectorStrokeReadableOnFills(topicBlue, ['#F04438'])).toBe(topicBlue)
    expect(connectorStrokeReadableOnFills(topicBlue, ['#12B76A'])).toBe(topicBlue)
    expect(connectorStrokeReadableOnFills(topicBlue, ['#1e293b'])).toBe(topicBlue)
    expect(connectorStrokeReadableOnFills(topicBlue, ['#0BA5EC'])).toBe('#1e293b')
    expect(connectorStrokeReadableOnFills(topicBlue, ['rgba(11,181,236,1)'])).toBe('#1e293b')
    expect(connectorStrokeReadableOnFills(topicBlue, ['#3B5BDB'])).toBe('#1e293b')
  })

  it('ignores an unknown theme id and keeps the palette', () => {
    const palette = getMindmapBranchColor(1).border
    expect(thinkingMapSolidThemeStroke('not-a-theme')).toBeNull()
    expect(resolveThinkingMapConnectorStroke('not-a-theme', palette, '#666')).toBe(palette)
  })
})
