import { describe, expect, it } from 'vitest'

import { extractMindmatePreviewCacheKey } from '@/utils/mindmateDiagramPreviewCache'
import {
  replaceMindmatePreviewImageUrl,
  stripMindmatePreviewImageMarkdown,
} from '@/utils/mindmateDiagramPreviewDisplay'

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

  it('replaces same-origin rewritten preview src with blob url', () => {
    const content = '![mg:abc](/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'
    expect(replaceMindmatePreviewImageUrl(content, 'blob:http://localhost/1')).toBe(
      '![mg:abc](blob:http://localhost/1)'
    )
  })

  it('replaces proxied preview src with blob url', () => {
    const remote =
      'https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    const content = `![](/api/proxy-image?url=${encodeURIComponent(remote)})`
    expect(replaceMindmatePreviewImageUrl(content, 'blob:cached')).toBe('![](blob:cached)')
  })
})

describe('stripMindmatePreviewImageMarkdown', () => {
  it('removes a dead generate_dingtalk preview image', () => {
    const content =
      'Here you go\n![](/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)\nThanks'
    expect(stripMindmatePreviewImageMarkdown(content)).toBe('Here you go\n\nThanks')
  })
})
