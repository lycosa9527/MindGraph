import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildShowcaseMindMateAttachment,
  formatShowcaseCaseMarkdown,
} from '@/composables/showcase/buildShowcaseMindMateAttachment'
import type { ShowcasePost } from '@/utils/apiClient'

vi.mock('@/utils/fetchShowcaseAsset', () => ({
  fetchShowcaseAsset: vi.fn(),
}))

import { fetchShowcaseAsset } from '@/utils/fetchShowcaseAsset'

function basePost(overrides: Partial<ShowcasePost> & { spec?: unknown } = {}): ShowcasePost & {
  spec?: unknown
} {
  return {
    id: 'post-1',
    title: '光合作用教学设计',
    description: '案例简介',
    tags: [],
    case_type: 'teaching_design',
    subject: '生物',
    grade: '初二',
    diagram_type: null,
    thumbnail_url: null,
    status: 'approved',
    is_expert_recommended: false,
    author: { id: 1, name: 'Teacher', avatar: null },
    likes_count: 0,
    views_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    is_liked: false,
    is_favorited: false,
    ...overrides,
  }
}

describe('formatShowcaseCaseMarkdown', () => {
  it('includes title, meta, highlights, and reflection', () => {
    const md = formatShowcaseCaseMarkdown(
      basePost({
        spec: {
          body: '课堂导入与探究',
          design_highlights: ['实验驱动', '分层提问'],
          teaching_reflection: '学生参与度高',
        },
      })
    )
    expect(md).toContain('# 光合作用教学设计')
    expect(md).toContain('学科：生物')
    expect(md).toContain('课堂导入与探究')
    expect(md).toContain('- 实验驱动')
    expect(md).toContain('学生参与度高')
  })
})

describe('buildShowcaseMindMateAttachment', () => {
  beforeEach(() => {
    vi.mocked(fetchShowcaseAsset).mockReset()
  })

  it('fetches attachment via showcase proxy and builds a File', async () => {
    vi.mocked(fetchShowcaseAsset).mockResolvedValue(
      new Response(new Uint8Array([1, 2, 3]), {
        status: 200,
        headers: { 'Content-Type': 'application/pdf' },
      })
    )
    const file = await buildShowcaseMindMateAttachment(
      basePost({
        attachment_url: '/api/showcase/assets/showcase/posts/post-1/plan.pdf',
        spec: { attachment_filename: 'plan.pdf' },
      })
    )
    expect(fetchShowcaseAsset).toHaveBeenCalledWith(
      '/api/showcase/assets/showcase/posts/post-1/plan.pdf'
    )
    expect(file.name).toBe('plan.pdf')
    expect(file.type).toBe('application/pdf')
    expect(file.size).toBe(3)
  })

  it('falls back to markdown when no attachment or preview exists', async () => {
    const file = await buildShowcaseMindMateAttachment(basePost())
    expect(fetchShowcaseAsset).not.toHaveBeenCalled()
    expect(file.name.endsWith('.md')).toBe(true)
    expect(file.type).toBe('text/markdown')
    const text = await file.text()
    expect(text).toContain('光合作用教学设计')
  })
})
