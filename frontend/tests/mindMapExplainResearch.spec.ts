import { describe, expect, it } from 'vitest'

import {
  applyExplainResearchEvent,
  citedExplainIndexes,
  emptyExplainResearchState,
  lastThinkingLines,
  RESEARCH_IMAGE_MAX,
  resolveExplainResearchPanelBox,
  resolveExplainResearchSide,
  splitExplainCitationParts,
  stepResearchStripScroll,
} from '@/utils/mindMapExplainResearch'

describe('applyExplainResearchEvent', () => {
  it('appends search cards and a found step as sources arrive', () => {
    const afterStatus = applyExplainResearchEvent(emptyExplainResearchState(), {
      event: 'status',
      phase: 'searching',
      query: '光合作用',
    })
    const afterSearch = applyExplainResearchEvent(afterStatus, {
      event: 'search_source',
      sources: [{ url: 'https://en.wikipedia.org/wiki/Photosynthesis', title: 'Photosynthesis' }],
    })

    expect(afterStatus.steps.map((step) => step.kind)).toEqual(['searching'])
    expect(afterSearch.sources).toEqual([
      {
        url: 'https://en.wikipedia.org/wiki/Photosynthesis',
        title: 'Photosynthesis',
        extracted: false,
      },
    ])
    expect(afterSearch.steps.at(-1)).toMatchObject({ kind: 'found', detail: '1' })
  })

  it('marks a source as read when extract finishes', () => {
    const withSource = applyExplainResearchEvent(emptyExplainResearchState(), {
      event: 'search_source',
      sources: [{ url: 'https://en.wikipedia.org/wiki/Photosynthesis' }],
    })
    const afterExtract = applyExplainResearchEvent(withSource, {
      event: 'extract',
      urls: ['https://en.wikipedia.org/wiki/Photosynthesis'],
    })

    expect(afterExtract.sources[0]?.extracted).toBe(true)
    expect(afterExtract.steps.some((step) => step.kind === 'read')).toBe(true)
  })

  it('streams images and then the summary without waiting for end', () => {
    const withImage = applyExplainResearchEvent(emptyExplainResearchState(), {
      event: 'image',
      images: [{ url: 'https://example.com/leaf.jpg', title: 'Leaf', index: 1 }],
    })
    const withToken = applyExplainResearchEvent(withImage, {
      event: 'token',
      text: '叶片',
    })
    const moreToken = applyExplainResearchEvent(withToken, {
      event: 'token',
      text: '把光变成糖。',
    })

    expect(withImage.images).toHaveLength(1)
    expect(withImage.phase).toBe('images')
    expect(moreToken.text).toBe('叶片把光变成糖。')
    expect(moreToken.steps.some((step) => step.kind === 'summarizing')).toBe(true)
  })

  it('keeps at most RESEARCH_IMAGE_MAX images', () => {
    const flood = Array.from({ length: RESEARCH_IMAGE_MAX + 8 }, (_, index) => ({
      url: `https://example.com/${index}.jpg`,
      title: `img-${index}`,
      index: index + 1,
    }))
    const after = applyExplainResearchEvent(emptyExplainResearchState(), {
      event: 'image',
      images: flood,
    })
    expect(after.images).toHaveLength(RESEARCH_IMAGE_MAX)
  })

  it('keeps only the last three thinking lines', () => {
    expect(lastThinkingLines('one\n\ntwo\nthree\nfour')).toBe('two\nthree\nfour')
    expect(lastThinkingLines('only one')).toBe('only one')
  })

  it('ping-pongs the image strip so every tile can scroll into view', () => {
    expect(stepResearchStripScroll(0, 400, 40, 1)).toEqual({ scrollLeft: 40, direction: 1 })
    expect(stepResearchStripScroll(390, 400, 40, 1)).toEqual({ scrollLeft: 400, direction: -1 })
    expect(stepResearchStripScroll(10, 400, 40, -1)).toEqual({ scrollLeft: 0, direction: 1 })
    expect(stepResearchStripScroll(80, 0, 40, 1)).toEqual({ scrollLeft: 0, direction: 1 })
  })

  it('parks images opposite the node on the mind map', () => {
    expect(resolveExplainResearchSide(-200, 0)).toBe('right')
    expect(resolveExplainResearchSide(240, 0)).toBe('left')
    expect(resolveExplainResearchSide(0, 0)).toBe('right')
    expect(resolveExplainResearchSide(undefined, 0)).toBe('right')
  })

  it('sizes the image panel to half the canvas', () => {
    const canvas = { left: 100, top: 40, width: 1000, height: 800 }
    expect(resolveExplainResearchPanelBox(canvas, 'right')).toEqual({
      left: 600,
      top: 52,
      width: 488,
      height: 776,
    })
    expect(resolveExplainResearchPanelBox(canvas, 'left').left).toBe(112)
    expect(resolveExplainResearchPanelBox({ ...canvas, width: 600 }, 'right').width).toBe(576)
  })

  it('splits DeepSeek-style [n] citations out of the gloss', () => {
    const parts = splitExplainCitationParts('叶片把光变成糖。[1][3] 这是代谢。[2]')
    expect(parts).toEqual([
      { kind: 'text', value: '叶片把光变成糖。' },
      { kind: 'cite', index: 1 },
      { kind: 'cite', index: 3 },
      { kind: 'text', value: ' 这是代谢。' },
      { kind: 'cite', index: 2 },
    ])
    expect(citedExplainIndexes('叶片把光变成糖。[1][3] 这是代谢。[2]')).toEqual([1, 3, 2])
  })

  it('accumulates thinking deltas separately from the gloss', () => {
    const first = applyExplainResearchEvent(emptyExplainResearchState(), {
      event: 'thinking',
      text: '先搜',
    })
    const second = applyExplainResearchEvent(first, {
      event: 'thinking',
      text: '再读',
    })
    expect(second.thinking).toBe('先搜再读')
    expect(second.text).toBe('')
    expect(second.thinkingDone).toBe(false)

    const afterSearch = applyExplainResearchEvent(second, {
      event: 'search_source',
      sources: [{ url: 'https://example.com', title: 'Example' }],
    })
    expect(afterSearch.thinkingDone).toBe(true)

    const imagesOnly = applyExplainResearchEvent(second, {
      event: 'image',
      images: [{ url: 'https://example.com/a.jpg', title: 'a', index: 1 }],
    })
    expect(imagesOnly.thinkingDone).toBe(false)
  })
})
