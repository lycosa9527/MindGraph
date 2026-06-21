import { describe, expect, it } from 'vitest'

import { MINDMAP_BRANCH_COLORS } from '@/config/mindmapColors'
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

  it('uses twelve distinct radix-inspired branch hues without duplicate borders', () => {
    expect(MINDMAP_BRANCH_COLORS.length).toBe(12)
    const borders = MINDMAP_BRANCH_COLORS.map((c) => c.border.toLowerCase())
    const unique = new Set(borders)
    expect(unique.size).toBe(borders.length)
  })
})
