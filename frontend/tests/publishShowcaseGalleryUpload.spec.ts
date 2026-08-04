import { describe, expect, it } from 'vitest'

import { countGalleryImagePathsInSpec } from '@/composables/showcase/publishShowcaseGalleryUpload'

describe('countGalleryImagePathsInSpec', () => {
  it('counts only image slots with a non-empty path', () => {
    expect(
      countGalleryImagePathsInSpec({
        gallery: [
          { kind: 'image', path: 'showcase/posts/a/gallery_0.png' },
          { kind: 'image', pending: true },
          { kind: 'diagram', diagram_id: 'd1' },
          { kind: 'image', path: '  ' },
        ],
      })
    ).toBe(1)
  })

  it('returns 0 for missing or invalid specs', () => {
    expect(countGalleryImagePathsInSpec(null)).toBe(0)
    expect(countGalleryImagePathsInSpec({})).toBe(0)
    expect(countGalleryImagePathsInSpec({ gallery: 'bad' })).toBe(0)
  })
})
