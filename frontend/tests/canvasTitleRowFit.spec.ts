import { describe, expect, it } from 'vitest'

import {
  type TitleRowFitMetrics,
  createTitleRowFitSnapshot,
  nextTitleRowFit,
} from '@/utils/canvasTitleRowFit'

function metrics(overrides: Partial<TitleRowFitMetrics> = {}): TitleRowFitMetrics {
  return {
    rowWidth: 1280,
    tabsWidth: 420,
    fixedWidth: 64,
    fullChromeWidth: 980,
    ...overrides,
  }
}

describe('nextTitleRowFit', () => {
  it('keeps filename, save, and collab when the centered tabs fit', () => {
    const next = nextTitleRowFit(createTitleRowFitSnapshot(), metrics())
    expect(next.mode).toBe('full')
  })

  it('hides the side chrome and keeps full tab text when the row is short', () => {
    const next = nextTitleRowFit(
      createTitleRowFitSnapshot(),
      metrics({ rowWidth: 720, fullChromeWidth: 980 })
    )
    expect(next.mode).toBe('textOnly')
    expect(next.fullChromeWidth).toBe(980)
  })

  it('stays text-only until the row can hold the full chrome again', () => {
    const tight = nextTitleRowFit(
      createTitleRowFitSnapshot(),
      metrics({ rowWidth: 720, fullChromeWidth: 980 })
    )
    const still = nextTitleRowFit(tight, metrics({ rowWidth: 900, tabsWidth: 280, fixedWidth: 64 }))
    expect(still.mode).toBe('textOnly')
    const restored = nextTitleRowFit(
      tight,
      metrics({ rowWidth: 1000, tabsWidth: 280, fixedWidth: 64 })
    )
    expect(restored.mode).toBe('full')
  })

  it('shortens tab text when text-only labels still overflow the back button', () => {
    const tight = nextTitleRowFit(
      createTitleRowFitSnapshot(),
      metrics({ rowWidth: 360, fullChromeWidth: 980 })
    )
    const short = nextTitleRowFit(tight, metrics({ rowWidth: 360, tabsWidth: 340, fixedWidth: 64 }))
    expect(short.mode).toBe('shortText')
    expect(short.textOnlyTabsWidth).toBe(340)
    const still = nextTitleRowFit(short, metrics({ rowWidth: 360, tabsWidth: 220, fixedWidth: 64 }))
    expect(still.mode).toBe('shortText')
  })

  it('restores full tab text once the text-only strip fits beside the back button', () => {
    const tight = nextTitleRowFit(
      createTitleRowFitSnapshot(),
      metrics({ rowWidth: 360, fullChromeWidth: 980 })
    )
    const short = nextTitleRowFit(tight, metrics({ rowWidth: 360, tabsWidth: 340, fixedWidth: 64 }))
    const textOnly = nextTitleRowFit(
      short,
      metrics({ rowWidth: 480, tabsWidth: 220, fixedWidth: 64 })
    )
    expect(textOnly.mode).toBe('textOnly')
  })

  it('ignores a row that has not been laid out', () => {
    const snapshot = createTitleRowFitSnapshot()
    expect(nextTitleRowFit(snapshot, metrics({ rowWidth: 0 }))).toBe(snapshot)
    expect(nextTitleRowFit(snapshot, metrics({ tabsWidth: 0 }))).toBe(snapshot)
    expect(nextTitleRowFit(snapshot, metrics({ rowWidth: Number.NaN }))).toBe(snapshot)
  })
})
