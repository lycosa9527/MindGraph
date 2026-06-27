import { describe, expect, it } from 'vitest'

import { extractMindmatePreviewCacheKey } from '@/utils/mindmateDiagramPreviewCache'
import { replaceMindmatePreviewImageUrl } from '@/utils/mindmateDiagramPreviewDisplay'

describe('extractMindmatePreviewCacheKey', () => {
  it('extracts dingtalk temp filename from preview markdown', () => {
    const content =
      '![](https://host/api/temp_images/dingtalk_DeadBeef_1710000000.png?sig=x&exp=1)'
    expect(extractMindmatePreviewCacheKey(content)).toBe('dingtalk_deadbeef_1710000000.png')
  })

  it('extracts dingtalk temp filename from same-origin image url', () => {
    expect(
      extractMindmatePreviewCacheKey('/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x')
    ).toBe('dingtalk_deadbeef_1710000000.png')
  })

  it('returns null for unrelated markdown', () => {
    expect(extractMindmatePreviewCacheKey('hello')).toBeNull()
  })
})

describe('replaceMindmatePreviewImageUrl', () => {
  it('replaces temp preview markdown src with blob url', () => {
    const content =
      '![mg:abc](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(replaceMindmatePreviewImageUrl(content, 'blob:cached')).toBe(
      '![mg:abc](blob:cached)'
    )
  })
})
