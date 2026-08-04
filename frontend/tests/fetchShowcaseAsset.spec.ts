import { describe, expect, it } from 'vitest'

import { withShowcaseAssetProxy } from '@/utils/fetchShowcaseAsset'

describe('withShowcaseAssetProxy', () => {
  it('adds proxy=1 for same-origin asset paths', () => {
    expect(withShowcaseAssetProxy('/api/showcase/assets/showcase/posts/a/attachment.pdf')).toBe(
      '/api/showcase/assets/showcase/posts/a/attachment.pdf?proxy=1'
    )
  })

  it('preserves existing query params', () => {
    expect(
      withShowcaseAssetProxy('/api/showcase/assets/showcase/posts/a/preview.pdf?x=1')
    ).toBe('/api/showcase/assets/showcase/posts/a/preview.pdf?x=1&proxy=1')
  })
})
