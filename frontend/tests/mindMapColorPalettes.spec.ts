import { describe, expect, it } from 'vitest'

import {
  getMindmapBranchColor,
  MINDMAP_BRANCH_COLORS,
  V2_MINDMAP_BRANCH_COLORS,
} from '@/config/mindmapColors'
import { LEGACY_MINDMAP_BRANCH_COLORS } from '@/config/mindMapLegacyColors'
import { MIND_MAP_THEMES } from '@/config/mindMapThemes'

describe('mind map color palettes', () => {
  it('defines curated themes with distinct topic accent colors', () => {
    expect(MIND_MAP_THEMES.length).toBeGreaterThanOrEqual(10)
    const topicBgs = MIND_MAP_THEMES.map((theme) => theme.topicBackgroundColor.toLowerCase())
    const unique = new Set(topicBgs)
    expect(unique.size).toBe(topicBgs.length)
  })

  it('documents a verifiable external source for each theme', () => {
    for (const theme of MIND_MAP_THEMES) {
      const note = theme.sourceNote.toLowerCase()
      const hasUrl =
        note.includes('http') ||
        note.includes('nordtheme') ||
        note.includes('radix-ui.com/colors')
      expect(hasUrl).toBe(true)
    }
  })

  it('uses Material-20 as the shared default palette (baseline 7c7df0d3)', () => {
    expect(MINDMAP_BRANCH_COLORS.length).toBe(20)
    expect(MINDMAP_BRANCH_COLORS[0]?.fill).toBe('#e3f2fd')
    expect(MINDMAP_BRANCH_COLORS[0]?.border).toBe('#0d47a1')
    expect(MINDMAP_BRANCH_COLORS).toBe(LEGACY_MINDMAP_BRANCH_COLORS)
    expect(getMindmapBranchColor(0).fill).toBe('#e3f2fd')
    expect(getMindmapBranchColor(0, 'legacy').border).toBe('#0d47a1')
  })

  it('keeps Radix-12 only for explicit v2 branch-index callers', () => {
    expect(V2_MINDMAP_BRANCH_COLORS.length).toBe(12)
    const borders = V2_MINDMAP_BRANCH_COLORS.map((c) => c.border.toLowerCase())
    expect(new Set(borders).size).toBe(borders.length)
    expect(getMindmapBranchColor(0, 'v2').fill).toBe('#e6f4fe')
    expect(getMindmapBranchColor(0, 'v2').border).toBe('#5eb1ef')
  })

  it('defines twenty material legacy mind-map branch hues for classic canvas', () => {
    expect(LEGACY_MINDMAP_BRANCH_COLORS.length).toBe(20)
    expect(LEGACY_MINDMAP_BRANCH_COLORS[0]?.fill).toBe('#e3f2fd')
    expect(LEGACY_MINDMAP_BRANCH_COLORS[0]?.border).toBe('#0d47a1')
  })
})
