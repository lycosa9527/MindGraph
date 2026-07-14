/** Diagram-case gallery items (images + saved diagrams). */

export const DIAGRAM_GALLERY_MAX_ITEMS = 12

export type ShowcaseGalleryImageItem = {
  kind: 'image'
  path?: string
  filename: string
  pending?: boolean
}

export type ShowcaseGalleryDiagramItem = {
  kind: 'diagram'
  diagram_id: string
  title: string
  diagram_type?: string
  spec?: Record<string, unknown>
}

export type ShowcaseGalleryItem = ShowcaseGalleryImageItem | ShowcaseGalleryDiagramItem

export type ShowcaseGalleryApiItem =
  | { kind: 'image'; url?: string | null; filename?: string | null; missing?: boolean }
  | {
      kind: 'diagram'
      diagram_id?: string | null
      title?: string | null
      diagram_type?: string | null
      spec?: Record<string, unknown>
    }

export function parseSpecGallery(spec: unknown): ShowcaseGalleryItem[] {
  if (!spec || typeof spec !== 'object') return []
  const gallery = (spec as Record<string, unknown>).gallery
  if (!Array.isArray(gallery)) return []
  const items: ShowcaseGalleryItem[] = []
  for (const raw of gallery) {
    if (!raw || typeof raw !== 'object') continue
    const entry = raw as Record<string, unknown>
    if (entry.kind === 'image' && typeof entry.filename === 'string') {
      items.push({
        kind: 'image',
        path: typeof entry.path === 'string' ? entry.path : undefined,
        filename: entry.filename,
      })
    } else if (entry.kind === 'diagram' && typeof entry.diagram_id === 'string') {
      items.push({
        kind: 'diagram',
        diagram_id: entry.diagram_id,
        title: typeof entry.title === 'string' ? entry.title : entry.diagram_id,
        diagram_type: typeof entry.diagram_type === 'string' ? entry.diagram_type : undefined,
        spec:
          entry.spec && typeof entry.spec === 'object'
            ? (entry.spec as Record<string, unknown>)
            : undefined,
      })
    }
  }
  return items
}

export function buildGallerySpecPayload(items: ShowcaseGalleryItem[]): ShowcaseGalleryItem[] {
  return items.map((item) => {
    if (item.kind === 'image') {
      const payload: ShowcaseGalleryImageItem = {
        kind: 'image',
        filename: item.filename,
      }
      if (item.path) payload.path = item.path
      if (!item.path) payload.pending = true
      return payload
    }
    const payload: ShowcaseGalleryDiagramItem = {
      kind: 'diagram',
      diagram_id: item.diagram_id,
      title: item.title,
    }
    if (item.diagram_type) payload.diagram_type = item.diagram_type
    if (item.spec) payload.spec = item.spec
    return payload
  })
}

export type ShowcaseCarouselSlide =
  | { kind: 'image'; url: string; filename?: string }
  | { kind: 'image'; url: null; filename?: string; missing: true }
  | {
      kind: 'diagram'
      diagram_id?: string
      title?: string
      diagram_type?: string
      spec?: Record<string, unknown>
    }

function staticUrlFromPath(path: string, resolveUrl: (url: string) => string | null): string | null {
  const normalized = path.replace(/^\/+/, '')
  return resolveUrl(`/static/${normalized}`)
}

function resolveImageSlideUrl(
  entry: ShowcaseGalleryImageItem,
  apiItem: ShowcaseGalleryApiItem | undefined,
  resolveUrl: (url: string | null | undefined) => string | null
): ShowcaseCarouselSlide {
  if (apiItem?.kind === 'image') {
    if (apiItem.missing || !apiItem.url) {
      return { kind: 'image', url: null, filename: entry.filename, missing: true }
    }
    const url = resolveUrl(apiItem.url)
    if (url) {
      return { kind: 'image', url, filename: apiItem.filename ?? entry.filename }
    }
    return { kind: 'image', url: null, filename: entry.filename, missing: true }
  }

  if (entry.path) {
    const url = staticUrlFromPath(entry.path, (u) => resolveUrl(u) ?? u)
    if (url) {
      return { kind: 'image', url, filename: entry.filename }
    }
  }

  return { kind: 'image', url: null, filename: entry.filename, missing: true }
}

function slidesFromSpecGallery(params: {
  specGallery: ShowcaseGalleryItem[]
  galleryItems?: ShowcaseGalleryApiItem[]
  resolveUrl: (url: string | null | undefined) => string | null
}): ShowcaseCarouselSlide[] {
  const slides: ShowcaseCarouselSlide[] = []

  for (let slot = 0; slot < params.specGallery.length; slot += 1) {
    const entry = params.specGallery[slot]
    const apiItem = params.galleryItems?.[slot]
    if (entry.kind === 'image') {
      slides.push(resolveImageSlideUrl(entry, apiItem, params.resolveUrl))
    } else {
      slides.push({
        kind: 'diagram',
        diagram_id: entry.diagram_id,
        title: entry.title,
        diagram_type: entry.diagram_type,
        spec: entry.spec ?? (apiItem?.kind === 'diagram' ? apiItem.spec : undefined),
      })
    }
  }
  return slides
}

function slidesFromApiGallery(
  galleryItems: ShowcaseGalleryApiItem[],
  resolveUrl: (url: string | null | undefined) => string | null
): ShowcaseCarouselSlide[] {
  const slides: ShowcaseCarouselSlide[] = []
  for (const item of galleryItems) {
    if (item.kind === 'image') {
      if (item.missing || !item.url) {
        slides.push({
          kind: 'image',
          url: null,
          filename: item.filename ?? undefined,
          missing: true,
        })
        continue
      }
      const url = resolveUrl(item.url)
      if (url) {
        slides.push({
          kind: 'image',
          url,
          filename: item.filename ?? undefined,
        })
      } else {
        slides.push({
          kind: 'image',
          url: null,
          filename: item.filename ?? undefined,
          missing: true,
        })
      }
    } else if (item.kind === 'diagram') {
      slides.push({
        kind: 'diagram',
        diagram_id: item.diagram_id ?? undefined,
        title: item.title ?? undefined,
        diagram_type: item.diagram_type ?? undefined,
        spec: item.spec,
      })
    }
  }
  return slides
}

/** Normalize API/spec/source fields into carousel slides for detail preview. */
export function resolveCarouselSlides(params: {
  galleryItems?: ShowcaseGalleryApiItem[]
  spec?: unknown
  postId?: string | null
  sourceFileUrl?: string | null
  thumbnailUrl?: string | null
  resolveUrl: (url: string | null | undefined) => string | null
}): ShowcaseCarouselSlide[] {
  const specGallery = parseSpecGallery(params.spec)

  if (specGallery.length > 1) {
    return slidesFromSpecGallery({
      specGallery,
      galleryItems: params.galleryItems,
      resolveUrl: params.resolveUrl,
    })
  }

  if (params.galleryItems?.length) {
    const fromApi = slidesFromApiGallery(params.galleryItems, params.resolveUrl)
    if (fromApi.length > 1) return fromApi
    if (fromApi.length === 1) return fromApi
  }

  if (specGallery.length === 1) {
    return slidesFromSpecGallery({
      specGallery,
      galleryItems: params.galleryItems,
      resolveUrl: params.resolveUrl,
    })
  }

  const slides: ShowcaseCarouselSlide[] = []
  const sourceUrl = params.resolveUrl(params.sourceFileUrl)
  if (sourceUrl && /\.(png|jpe?g|webp|gif)(\?|$)/i.test(sourceUrl)) {
    slides.push({ kind: 'image', url: sourceUrl })
  } else if (params.resolveUrl(params.thumbnailUrl)) {
    const thumb = params.resolveUrl(params.thumbnailUrl)!
    slides.push({ kind: 'image', url: thumb })
  }

  return slides
}
