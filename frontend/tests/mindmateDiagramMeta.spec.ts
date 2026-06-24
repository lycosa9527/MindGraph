import { describe, expect, it } from 'vitest'

import {
  extractMindmatePreviewUniqueId,
  extractFirstMarkdownImageUrl,
  hasGeneratedDiagramImage,
  hasLibraryFullNotice,
  isImagePrimaryAnswer,
  needsLibraryFullHint,
  needsLibrarySaveHint,
  parseMindmateDiagramLibraryId,
  rewriteMindmateTempImageUrls,
  stripMindmateDiagramIdComments,
} from '@/utils/mindmateDiagramMeta'

describe('parseMindmateDiagramLibraryId', () => {
  it('parses diagram id marker comment', () => {
    const content = '![](https://x/t.png)\n<!-- mg-diagram-id:abc-123 -->'
    expect(parseMindmateDiagramLibraryId(content)).toBe('abc-123')
  })

  it('parses diagram id from mg alt text', () => {
    const content =
      '![mg:550e8400-e29b-41d4-a716-446655440000](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(parseMindmateDiagramLibraryId(content)).toBe('550e8400-e29b-41d4-a716-446655440000')
  })

  it('parses diagram id from mgdid query param in preview url', () => {
    const uuid = '550e8400-e29b-41d4-a716-446655440000'
    const content = `![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&mgdid=${uuid})`
    expect(parseMindmateDiagramLibraryId(content)).toBe(uuid)
  })

  it('returns null when only preview image is present', () => {
    const content = '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(parseMindmateDiagramLibraryId(content)).toBeNull()
  })

  it('returns null for unrelated markdown', () => {
    expect(parseMindmateDiagramLibraryId('hello world')).toBeNull()
  })
})

describe('stripMindmateDiagramIdComments', () => {
  it('removes all mg-diagram-id HTML comments from display markdown', () => {
    const content =
      '![](https://x/t.png)\n<!-- mg-diagram-id:abc-123 --> <!-- mg-diagram-id:def-456 -->'
    expect(stripMindmateDiagramIdComments(content)).toBe('![](https://x/t.png)')
    expect(parseMindmateDiagramLibraryId(content)).toBe('abc-123')
  })
})

describe('extractFirstMarkdownImageUrl', () => {
  it('returns rewritten same-origin url for temp diagram png', () => {
    const content =
      '![mg:abc](http://localhost:9527/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(extractFirstMarkdownImageUrl(content, 'localhost:41732')).toBe(
      '/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    )
  })
})

describe('isImagePrimaryAnswer', () => {
  it('returns true for diagram-only markdown', () => {
    const content = '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(isImagePrimaryAnswer(content)).toBe(true)
  })

  it('returns false when prose accompanies the image', () => {
    const content =
      'Here is your diagram:\n![](https://host/temp_images/dingtalk_deadbeef_1710000000.png)'
    expect(isImagePrimaryAnswer(content)).toBe(false)
  })
})

describe('hasGeneratedDiagramImage', () => {
  it('detects generate_dingtalk preview urls', () => {
    const content = '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(hasGeneratedDiagramImage(content)).toBe(true)
  })

  it('returns false for unrelated images', () => {
    expect(hasGeneratedDiagramImage('![](https://example.com/photo.png)')).toBe(false)
  })
})

describe('extractMindmatePreviewUniqueId', () => {
  it('extracts temp png id from preview url', () => {
    const content = '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(extractMindmatePreviewUniqueId(content)).toBe('deadbeef')
  })
})

describe('hasLibraryFullNotice', () => {
  it('detects library full notice in markdown', () => {
    const content = '![](url)\n图库已满，请在 MindGraph 删除旧图后再试。'
    expect(hasLibraryFullNotice(content)).toBe(true)
  })
})

describe('needsLibraryFullHint', () => {
  it('returns true for preview with full notice and no uuid', () => {
    const content =
      '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png)\n图库已满，请在 MindGraph 删除旧图后再试。'
    expect(needsLibraryFullHint(content)).toBe(true)
  })
})

describe('rewriteMindmateTempImageUrls', () => {
  it('rewrites absolute temp image urls to same-origin api path', () => {
    const content =
      '![](http://localhost:9527/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'
    expect(rewriteMindmateTempImageUrls(content)).toBe(
      '![](/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'
    )
  })
})

describe('needsLibrarySaveHint', () => {
  it('returns true when preview exists without library uuid', () => {
    const content = '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png)'
    expect(needsLibrarySaveHint(content)).toBe(true)
  })

  it('returns false when library uuid is present', () => {
    const content = '![mg:abc-123](https://host/temp_images/dingtalk_deadbeef_1710000000.png)'
    expect(needsLibrarySaveHint(content)).toBe(false)
  })

  it('returns false when library uuid is in mgdid url param', () => {
    const content =
      '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&mgdid=550e8400-e29b-41d4-a716-446655440000)'
    expect(needsLibrarySaveHint(content)).toBe(false)
  })

  it('returns false when backend skip notice is already in markdown', () => {
    const content =
      '![](https://host/temp_images/dingtalk_deadbeef_1710000000.png)\nDiagram preview only — bind DingTalk'
    expect(needsLibrarySaveHint(content)).toBe(false)
  })
})
