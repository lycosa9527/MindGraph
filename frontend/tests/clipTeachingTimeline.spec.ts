import { describe, expect, it } from 'vitest'

import {
  chapterSegments,
  clampPlayhead,
  playbackBounds,
  seekMsForRatio,
} from '@/utils/clipTeachingTimeline'

describe('clip teaching timeline', () => {
  it('clamps playback to the trim and pauses at the end', () => {
    expect(playbackBounds(1000, 5000, 9000)).toEqual({ startMs: 1000, endMs: 5000 })
    expect(playbackBounds(1000, null, 9000)).toEqual({ startMs: 1000, endMs: 9000 })
    expect(clampPlayhead(200, 1000, 5000, true)).toEqual({ seekMs: 1000, pause: false })
    expect(clampPlayhead(5000, 1000, 5000, true)).toEqual({ seekMs: null, pause: true })
    expect(clampPlayhead(2000, 1000, 5000, true)).toEqual({ seekMs: null, pause: false })
    expect(clampPlayhead(200, 1000, 5000, false)).toEqual({ seekMs: null, pause: false })
  })

  it('turns chapter starts into segments across the trim', () => {
    const segments = chapterSegments(
      [
        { id: 'b', title: '第二段', startMs: 3000 },
        { id: 'a', title: '第一段', startMs: 1000 },
      ],
      0,
      8000
    )
    expect(segments.map((segment) => [segment.id, segment.startMs, segment.endMs])).toEqual([
      ['lead', 0, 1000],
      ['a', 1000, 3000],
      ['b', 3000, 8000],
    ])
    expect(seekMsForRatio(0.25, 0, 8000)).toBe(2000)
    expect(seekMsForRatio(2, 0, 8000)).toBe(8000)
  })
})
