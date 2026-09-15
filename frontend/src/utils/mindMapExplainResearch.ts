/**
 * Pure SSE reducers for mind-map node-explain research.
 */

export const RESEARCH_IMAGE_MAX = 24
export const RESEARCH_IMAGE_REVEAL_MS = 80
export const RESEARCH_IMAGE_SCROLL_PX_PER_SEC = 80
export const THINKING_LINE_MAX = 3
export type ExplainResearchSide = 'left' | 'right'

export function researchStripMaxScroll(width: number, viewport: number): number {
  return Math.max(0, width - viewport)
}

export function stepResearchStripScroll(
  scrollLeft: number,
  maxScroll: number,
  deltaPx: number,
  direction: 1 | -1
): { scrollLeft: number; direction: 1 | -1 } {
  if (maxScroll <= 0) return { scrollLeft: 0, direction: 1 }
  const next = scrollLeft + deltaPx * direction
  if (next >= maxScroll) return { scrollLeft: maxScroll, direction: -1 }
  if (next <= 0) return { scrollLeft: 0, direction: 1 }
  return { scrollLeft: next, direction }
}

export function resolveExplainResearchSide(
  nodeX: number | undefined,
  topicX: number | undefined
): ExplainResearchSide {
  if (typeof nodeX !== 'number' || typeof topicX !== 'number') return 'right'
  return nodeX <= topicX ? 'right' : 'left'
}

export const RESEARCH_PANEL_CANVAS_SHARE = 0.5
export const RESEARCH_PANEL_NARROW_PX = 720
export const RESEARCH_PANEL_INSET_PX = 12

export type ExplainResearchPanelBox = {
  left: number
  top: number
  width: number
  height: number
}

export function resolveExplainResearchPanelBox(
  canvas: { left: number; top: number; width: number; height: number },
  side: ExplainResearchSide,
  inset = RESEARCH_PANEL_INSET_PX
): ExplainResearchPanelBox {
  const top = canvas.top + inset
  const height = Math.max(0, canvas.height - inset * 2)
  if (canvas.width < RESEARCH_PANEL_NARROW_PX) {
    return {
      left: canvas.left + inset,
      top,
      width: Math.max(0, canvas.width - inset * 2),
      height,
    }
  }
  const half = canvas.width * RESEARCH_PANEL_CANVAS_SHARE
  if (side === 'left') {
    return { left: canvas.left + inset, top, width: Math.max(0, half - inset), height }
  }
  return {
    left: canvas.left + canvas.width - half,
    top,
    width: Math.max(0, half - inset),
    height,
  }
}

export type ExplainTextPart = { kind: 'text'; value: string } | { kind: 'cite'; index: number }

export function splitExplainCitationParts(text: string): ExplainTextPart[] {
  const parts: ExplainTextPart[] = []
  const pattern = /\[(\d+)\]/g
  let lastIndex = 0
  let match = pattern.exec(text)
  while (match) {
    if (match.index > lastIndex) {
      parts.push({ kind: 'text', value: text.slice(lastIndex, match.index) })
    }
    parts.push({ kind: 'cite', index: Number(match[1]) })
    lastIndex = match.index + match[0].length
    match = pattern.exec(text)
  }
  if (lastIndex < text.length) {
    parts.push({ kind: 'text', value: text.slice(lastIndex) })
  }
  return parts
}

export function citedExplainIndexes(text: string): number[] {
  const seen = new Set<number>()
  const indexes: number[] = []
  splitExplainCitationParts(text).forEach((part) => {
    if (part.kind !== 'cite' || seen.has(part.index)) return
    seen.add(part.index)
    indexes.push(part.index)
  })
  return indexes
}

export function lastThinkingLines(text: string, max = THINKING_LINE_MAX): string {
  const lines = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (lines.length <= max) return lines.join('\n')
  return lines.slice(-max).join('\n')
}

export type ExplainResearchPhase = 'searching' | 'extracting' | 'images' | 'summarizing' | ''

export type ExplainResearchStepKind =
  | 'searching'
  | 'found'
  | 'reading'
  | 'read'
  | 'images'
  | 'summarizing'

export type ExplainResearchStep = {
  id: string
  kind: ExplainResearchStepKind
  detail: string
}

export type ExplainResearchSource = {
  url: string
  title: string
  extracted: boolean
}

export type ExplainResearchImage = {
  url: string
  title: string
  index: number
}

export type ExplainResearchState = {
  text: string
  thinking: string
  thinkingDone: boolean
  phase: ExplainResearchPhase
  steps: ExplainResearchStep[]
  sources: ExplainResearchSource[]
  images: ExplainResearchImage[]
}

export function emptyExplainResearchState(): ExplainResearchState {
  return {
    text: '',
    thinking: '',
    thinkingDone: false,
    phase: '',
    steps: [],
    sources: [],
    images: [],
  }
}

export function hostFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function pushStep(
  state: ExplainResearchState,
  kind: ExplainResearchStepKind,
  detail: string
): ExplainResearchState {
  const last = state.steps[state.steps.length - 1]
  if (last && last.kind === kind && last.detail === detail) {
    return state
  }
  return {
    ...state,
    steps: [...state.steps, { id: `${kind}-${state.steps.length}`, kind, detail }],
  }
}

function mergeSources(
  existing: ExplainResearchSource[],
  incoming: Array<{ url?: unknown; title?: unknown }>,
  extracted: boolean
): ExplainResearchSource[] {
  const next = [...existing]
  incoming.forEach((item) => {
    const url = typeof item.url === 'string' ? item.url.trim() : ''
    if (!url) return
    const title = typeof item.title === 'string' && item.title.trim() ? item.title.trim() : hostFromUrl(url)
    const index = next.findIndex((source) => source.url === url)
    if (index >= 0) {
      const current = next[index]
      next[index] = {
        url,
        title: title || current.title,
        extracted: current.extracted || extracted,
      }
      return
    }
    next.push({ url, title, extracted })
  })
  return next
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

function markThinkingDone(state: ExplainResearchState): ExplainResearchState {
  if (state.thinkingDone || !state.thinking.trim()) return state
  return { ...state, thinkingDone: true }
}

export function applyExplainResearchEvent(
  state: ExplainResearchState,
  eventPayload: Record<string, unknown>
): ExplainResearchState {
  const event = eventPayload.event
  if (event === 'token' && typeof eventPayload.text === 'string') {
    const next = markThinkingDone(
      state.phase === 'summarizing' ? state : pushStep(state, 'summarizing', '')
    )
    return { ...next, phase: 'summarizing', text: next.text + eventPayload.text }
  }
  if (event === 'thinking' && typeof eventPayload.text === 'string') {
    return { ...state, thinking: state.thinking + eventPayload.text }
  }
  if (event === 'status') {
    const phase = typeof eventPayload.phase === 'string' ? eventPayload.phase : ''
    const query = typeof eventPayload.query === 'string' ? eventPayload.query : ''
    const urls = asStringList(eventPayload.urls)
    if (phase === 'searching') {
      return { ...markThinkingDone(pushStep(state, 'searching', query)), phase: 'searching' }
    }
    if (phase === 'extracting') {
      const host = urls[0] ? hostFromUrl(urls[0]) : ''
      return { ...markThinkingDone(pushStep(state, 'reading', host)), phase: 'extracting' }
    }
    if (phase === 'images') {
      return { ...pushStep(state, 'images', ''), phase: 'images' }
    }
    return state
  }
  if (event === 'search_source') {
    const rawSources = Array.isArray(eventPayload.sources) ? eventPayload.sources : []
    const sources = mergeSources(
      state.sources,
      rawSources as Array<{ url?: unknown; title?: unknown }>,
      false
    )
    return {
      ...markThinkingDone(pushStep(state, 'found', String(sources.length))),
      sources,
      phase: 'searching',
    }
  }
  if (event === 'extract') {
    const urls = asStringList(eventPayload.urls)
    const sources = mergeSources(
      state.sources,
      urls.map((url) => ({ url, title: hostFromUrl(url) })),
      true
    )
    const host = urls[0] ? hostFromUrl(urls[0]) : ''
    return { ...markThinkingDone(pushStep(state, 'read', host)), sources, phase: 'extracting' }
  }
  if (event === 'image') {
    if (state.images.length >= RESEARCH_IMAGE_MAX) return state
    const raw = Array.isArray(eventPayload.images) ? eventPayload.images : []
    const images = [...state.images]
    raw.forEach((item) => {
      if (images.length >= RESEARCH_IMAGE_MAX) return
      if (!item || typeof item !== 'object') return
      const record = item as { url?: unknown; title?: unknown; index?: unknown }
      const url = typeof record.url === 'string' ? record.url.trim() : ''
      if (!url || images.some((image) => image.url === url)) return
      images.push({
        url,
        title: typeof record.title === 'string' ? record.title : '',
        index: typeof record.index === 'number' ? record.index : images.length + 1,
      })
    })
    return { ...pushStep(state, 'images', ''), images, phase: 'images' }
  }
  return state
}
