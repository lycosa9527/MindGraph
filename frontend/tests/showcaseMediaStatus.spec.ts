import { describe, expect, it } from 'vitest'

import {
  resolveShowcaseMediaStatus,
  showcaseCoverJobTooltip,
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
    expect(
      resolveShowcaseMediaStatus(basePost({ media_status: 'preview_failed' }))
    ).toBe('preview_failed')
    expect(
      resolveShowcaseMediaStatus(basePost({ media_status: 'cover_failed' }))
    ).toBe('cover_failed')
    expect(
      resolveShowcaseMediaStatus(basePost({ media_status: 'generating_cover' }))
    ).toBe('generating_cover')
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

  it('derives generating_cover for in-flight native PDF', () => {
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.pdf',
          cover_job: {
            status: 'running',
            attempt_count: 1,
            current_stage: 'upload',
          },
        })
      )
    ).toBe('generating_cover')
  })

  it('derives preview_failed for failed Office without preview', () => {
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.docx',
          cover_job: {
            status: 'failed',
            attempt_count: 2,
            error_message: 'libreoffice failed',
            current_stage: 'convert',
          },
        })
      )
    ).toBe('preview_failed')
  })

  it('derives cover_failed when preview exists but thumb missing', () => {
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.docx',
          preview_url: '/api/showcase/assets/showcase/posts/a/preview.pdf',
          cover_job: {
            status: 'failed',
            attempt_count: 1,
            error_message: 'render failed',
            current_stage: 'upload',
          },
        })
      )
    ).toBe('cover_failed')
  })

  it('derives cover_ready when cover and preview both exist', () => {
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
    expect(showcaseMediaStatusLabelKey('generating_cover')).toBe(
      'admin.showcase.mediaStatus.generating_cover'
    )
    expect(showcaseMediaStatusLabelKey('preview_failed')).toBe(
      'admin.showcase.mediaStatus.preview_failed'
    )
    expect(showcaseMediaStatusChipClass('cover_ready')).toContain('emerald')
    expect(showcaseMediaStatusChipClass('converting_preview')).toContain('amber')
    expect(showcaseMediaStatusChipClass('generating_cover')).toContain('amber')
    expect(showcaseMediaStatusChipClass('preview_failed')).toContain('red')
    expect(showcaseMediaStatusChipClass('cover_failed')).toContain('red')
    expect(showcaseMediaStatusChipClass('conversion_failed')).toContain('red')
  })

  it('includes stage in cover job tooltip when failed', () => {
    expect(
      showcaseCoverJobTooltip(
        basePost({
          cover_job: {
            status: 'failed',
            attempt_count: 2,
            current_stage: 'convert',
            error_message: 'libreoffice failed',
          },
        })
      )
    ).toBe('stage: convert · libreoffice failed · attempts: 2')
  })

  it('ignores stale in-flight cover_job when deriving status', () => {
    const staleUpdatedAt = new Date(Date.now() - 400_000).toISOString()
    expect(
      resolveShowcaseMediaStatus(
        basePost({
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.pdf',
          preview_url: undefined,
          thumbnail_url: '/api/showcase/assets/showcase/posts/a/thumbnail.png',
          cover_job: {
            status: 'running',
            attempt_count: 1,
            current_stage: 'upload',
            updated_at: staleUpdatedAt,
          },
        })
      )
    ).toBe('cover_ready')
  })

  it('hides tooltip for terminal ready with stale in-flight job', () => {
    const staleUpdatedAt = new Date(Date.now() - 400_000).toISOString()
    expect(
      showcaseCoverJobTooltip(
        basePost({
          media_status: 'cover_ready',
          attachment_url: '/api/showcase/assets/showcase/posts/a/attachment.pdf',
          thumbnail_url: '/api/showcase/assets/showcase/posts/a/thumbnail.png',
          cover_job: {
            status: 'running',
            attempt_count: 1,
            current_stage: 'upload',
            updated_at: staleUpdatedAt,
          },
        })
      )
    ).toBe('')
  })
})
