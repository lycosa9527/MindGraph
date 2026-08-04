import { describe, expect, it } from 'vitest'

import {
  resolveShowcaseMediaStatus,
  showcaseMediaStatusChipClass,
  showcaseMediaStatusLabelKey,
} from '@/composables/admin/showcaseMediaStatus'
import type { ShowcasePost } from '@/utils/apiClient'

function basePost(overrides: Partial<ShowcasePost> = {}): ShowcasePost {
  return {
    id: 'p1',
    title: 'Case',
    description: null,
    tags: [],
    case_type: 'teaching_design',
    subject: null,
    grade: null,
    diagram_type: null,
    thumbnail_url: null,
    status: 'pending',
    is_expert_recommended: false,
    author: { id: 1, name: 'A', avatar: null },
    likes_count: 0,
    views_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    is_liked: false,
    is_favorited: false,
    ...overrides,
  }
}

describe('resolveShowcaseMediaStatus', () => {
  it('prefers API media_status', () => {
    expect(
      resolveShowcaseMediaStatus(basePost({ media_status: 'conversion_failed' }))
    ).toBe('conversion_failed')
  })

  it('derives converting_preview for Office attachments', () => {
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.docx',
        })
      )
    ).toBe('converting_preview')
  })

  it('derives cover_ready when thumbnail and preview exist', () => {
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.docx',
          preview_url: '/api/showcase/assets/showcase/posts/a/preview.pdf',
          thumbnail_url: '/api/showcase/assets/showcase/posts/a/thumbnail.png',
        })
      )
    ).toBe('cover_ready')
  })
})

describe('showcaseMediaStatus helpers', () => {
  it('maps label keys and chip classes', () => {
    expect(showcaseMediaStatusLabelKey('preview_ready')).toBe(
      'admin.showcase.mediaStatus.preview_ready'
    )
    expect(showcaseMediaStatusChipClass('cover_ready')).toContain('emerald')
    expect(showcaseMediaStatusChipClass('converting_preview')).toContain('amber')
  })
})
