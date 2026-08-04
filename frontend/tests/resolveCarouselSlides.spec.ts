import { describe, expect, it } from 'vitest'

import { resolveCarouselSlides } from '@/components/showcase/showcaseGallery'

const identity = (url: string | null | undefined): string | null => url ?? null

describe('resolveCarouselSlides', () => {
  it('prefers interactive diagram over cover thumbnail when top-level spec is renderable', () => {
    const slides = resolveCarouselSlides({
      spec: {
        topic: '全等三角形',
        children: [{ text: '对应边相等' }],
      },
      thumbnailUrl: '/static/showcase/posts/x/thumbnail.png',
      diagramType: 'mind_map',
      resolveUrl: identity,
    })

    expect(slides).toHaveLength(1)
    expect(slides[0]).toMatchObject({
      kind: 'diagram',
      diagram_type: 'mind_map',
    })
    if (slides[0].kind === 'diagram') {
      expect(slides[0].spec).toMatchObject({ topic: '全等三角形' })
    }
  })

  it('prefers interactive diagram over thumbnail when source is a .mg file', () => {
    const slides = resolveCarouselSlides({
      sourceFileUrl: '/static/showcase/posts/x/source.mg',
      thumbnailUrl: '/static/showcase/posts/x/thumbnail.png',
      diagramType: 'bubble_map',
      resolveUrl: identity,
    })

    expect(slides).toEqual([
      {
        kind: 'diagram',
        diagram_type: 'bubble_map',
      },
    ])
  })

  it('falls back to thumbnail image when there is no diagram graph data', () => {
    const slides = resolveCarouselSlides({
      spec: { source: 'image_upload' },
      thumbnailUrl: '/static/showcase/posts/x/thumbnail.png',
      resolveUrl: identity,
    })

    expect(slides).toEqual([
      {
        kind: 'image',
        url: '/static/showcase/posts/x/thumbnail.png',
      },
    ])
  })

  it('keeps a single gallery diagram slide', () => {
    const diagramSpec = { topic: '相似三角形', children: [] }
    const slides = resolveCarouselSlides({
      galleryItems: [
        {
          kind: 'diagram',
          diagram_id: 'd1',
          title: '对比',
          diagram_type: 'double_bubble_map',
          spec: diagramSpec,
        },
      ],
      thumbnailUrl: '/static/showcase/posts/x/thumbnail.png',
      resolveUrl: identity,
    })

    expect(slides).toEqual([
      {
        kind: 'diagram',
        diagram_id: 'd1',
        title: '对比',
        diagram_type: 'double_bubble_map',
        spec: diagramSpec,
      },
    ])
  })

  it('prefers top-level diagram over a lone gallery cover image', () => {
    const slides = resolveCarouselSlides({
      galleryItems: [
        {
          kind: 'image',
          url: '/static/showcase/posts/x/gallery_0.png',
          filename: 'cover.png',
        },
      ],
      spec: {
        topic: '中心主题',
        nodes: [{ id: '1', text: 'A' }],
      },
      thumbnailUrl: '/static/showcase/posts/x/thumbnail.png',
      diagramType: 'mind_map',
      resolveUrl: identity,
    })

    expect(slides).toHaveLength(1)
    expect(slides[0].kind).toBe('diagram')
  })
})
