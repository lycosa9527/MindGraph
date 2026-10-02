import { describe, expect, it } from 'vitest'

import { getMindMapThemeById } from '@/config/mindMapThemes'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  resolveThinkingMapConnectorStroke,
  thinkingMapSolidThemeStroke,
} from '@/utils/thinkingMapConnectionStroke'

describe('thinking map connection stroke', () => {
  it('keeps the per-branch palette on the default rainbow theme', () => {
    const palette = getMindmapBranchColor(2).border
    expect(thinkingMapSolidThemeStroke(undefined)).toBeNull()
    expect(thinkingMapSolidThemeStroke(null)).toBeNull()
    expect(thinkingMapSolidThemeStroke('rainbow')).toBeNull()
    expect(resolveThinkingMapConnectorStroke('rainbow', palette, '#666')).toBe(palette)
    expect(resolveThinkingMapConnectorStroke(undefined, undefined, '#666')).toBe('#666')
  })

  it('paints every connector with the solid theme accent', () => {
    const accent = getMindMapThemeById('vibrantOrange').borderColor
    const palette = getMindmapBranchColor(0).border
    expect(thinkingMapSolidThemeStroke('vibrantOrange')).toBe(accent)
    expect(accent).not.toBe(palette)
    expect(resolveThinkingMapConnectorStroke('vibrantOrange', palette, '#94a3b8')).toBe(accent)
    expect(resolveThinkingMapConnectorStroke('vibrantOrange', undefined, '#94a3b8')).toBe(accent)
  })

  it('ignores an unknown theme id and keeps the palette', () => {
    const palette = getMindmapBranchColor(1).border
    expect(thinkingMapSolidThemeStroke('not-a-theme')).toBeNull()
    expect(resolveThinkingMapConnectorStroke('not-a-theme', palette, '#666')).toBe(palette)
  })
})
