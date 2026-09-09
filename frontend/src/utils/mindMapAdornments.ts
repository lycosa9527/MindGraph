/**
 * Path-keyed mind-map node adornments (icon, href, image).
 */
import type {
  Connection,
  DiagramData,
  DiagramNode,
  MindMapAdornmentsByPath,
  MindMapNodeAdornment,
} from '@/types'
import { MINDMAP_TOPIC_ID, mindMapLocationPathKey } from '@/utils/mindMapLocation'

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

function parseAdornment(raw: unknown): MindMapNodeAdornment | null {
  if (!isPlainObject(raw)) return null
  const icon = typeof raw.icon === 'string' ? raw.icon.trim() : ''
  const href = typeof raw.href === 'string' ? raw.href.trim() : ''
  const imageUrl = typeof raw.imageUrl === 'string' ? raw.imageUrl.trim() : ''
  const next: MindMapNodeAdornment = {}
  if (icon) next.icon = icon
  if (href) next.href = href
  if (imageUrl) next.imageUrl = imageUrl
  return Object.keys(next).length > 0 ? next : null
}

export function parseMindMapAdornments(raw: unknown): MindMapAdornmentsByPath {
  if (!isPlainObject(raw)) return {}
  const out: MindMapAdornmentsByPath = {}
  for (const [path, value] of Object.entries(raw)) {
    if (!path) continue
    const parsed = parseAdornment(value)
    if (parsed) out[path] = parsed
  }
  return out
}

export function readMindMapAdornments(
  data: Record<string, unknown> | DiagramData | null | undefined
): MindMapAdornmentsByPath {
  if (!data) return {}
  return parseMindMapAdornments((data as Record<string, unknown>)._mindmap_adornments)
}

export function writeMindMapAdornments(
  data: Record<string, unknown> | DiagramData,
  adornments: MindMapAdornmentsByPath
): void {
  const record = data as Record<string, unknown>
  if (Object.keys(adornments).length === 0) {
    delete record._mindmap_adornments
    return
  }
  record._mindmap_adornments = adornments
}

export function mindMapAdornmentPathKey(
  nodeId: string,
  connections: readonly Connection[]
): string | null {
  if (nodeId === MINDMAP_TOPIC_ID) return MINDMAP_TOPIC_ID
  return mindMapLocationPathKey(nodeId, connections)
}

export function readNodeAdornment(
  data: Record<string, unknown> | DiagramData | null | undefined,
  nodeId: string,
  connections: readonly Connection[] | undefined
): MindMapNodeAdornment | null {
  const path = mindMapAdornmentPathKey(nodeId, connections ?? [])
  if (!path) return null
  const all = readMindMapAdornments(data)
  return all[path] ?? null
}

export type MindMapAdornmentPart = 'all' | 'image' | 'inline'

export function resolveMindMapAdornmentParts(
  part: MindMapAdornmentPart,
  hasImage: boolean,
  hasInline: boolean
): { image: boolean; inline: boolean } {
  return {
    image: hasImage && part !== 'inline',
    inline: hasInline && part !== 'image',
  }
}

export function mergeNodeAdornment(
  current: MindMapNodeAdornment | undefined,
  patch: MindMapNodeAdornment
): MindMapNodeAdornment | undefined {
  const next: MindMapNodeAdornment = { ...(current ?? {}) }
  if (patch.icon !== undefined) {
    if (patch.icon) next.icon = patch.icon
    else delete next.icon
  }
  if (patch.href !== undefined) {
    if (patch.href) next.href = patch.href
    else delete next.href
  }
  if (patch.imageUrl !== undefined) {
    if (patch.imageUrl) next.imageUrl = patch.imageUrl
    else delete next.imageUrl
  }
  return Object.keys(next).length > 0 ? next : undefined
}

const BLOCKED_HREF_SCHEMES = /^(javascript|data|vbscript|file):/i

/** Allow http(s), mailto, and protocol-relative / site-relative paths. */
export function sanitizeMindMapHref(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  if (BLOCKED_HREF_SCHEMES.test(trimmed)) return null
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (/^mailto:/i.test(trimmed)) return trimmed
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) return trimmed
  if (trimmed.startsWith('//') && /^\/\/[^\s/]+/.test(trimmed)) return `https:${trimmed}`
  if (/^[a-z0-9][a-z0-9-]*\.[a-z]{2,}([/:?#].*)?$/i.test(trimmed)) {
    return `https://${trimmed}`
  }
  return null
}

const DATA_URL_IMAGE_RE = /^data:image\/(png|jpe?g|gif|webp);base64,/i
const HTTP_IMAGE_RE = /^https?:\/\/\S+/i

export function sanitizeMindMapImageUrl(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  if (DATA_URL_IMAGE_RE.test(trimmed)) return trimmed
  if (HTTP_IMAGE_RE.test(trimmed)) return trimmed
  return null
}

export const MINDMAP_NODE_IMAGE_MAX_DATA_URL_CHARS = 280_000

export function isMindMapImageDataUrlOverCap(dataUrl: string): boolean {
  return dataUrl.length > MINDMAP_NODE_IMAGE_MAX_DATA_URL_CHARS
}

export function remapMindMapAdornmentsAfterReload(
  adornments: MindMapAdornmentsByPath,
  oldNodes: DiagramNode[],
  oldConnections: Connection[],
  newNodes: DiagramNode[],
  newConnections: Connection[],
  remapNodeId: (
    oldId: string,
    oldNodes: DiagramNode[],
    oldConnections: Connection[],
    newNodes: DiagramNode[],
    newConnections: Connection[]
  ) => string | null
): MindMapAdornmentsByPath {
  const next: MindMapAdornmentsByPath = {}
  for (const [path, adornment] of Object.entries(adornments)) {
    const oldId =
      path === MINDMAP_TOPIC_ID
        ? MINDMAP_TOPIC_ID
        : oldNodes.find((node) => mindMapLocationPathKey(node.id, oldConnections) === path)?.id
    if (!oldId) continue
    const newId =
      oldId === MINDMAP_TOPIC_ID
        ? MINDMAP_TOPIC_ID
        : remapNodeId(oldId, oldNodes, oldConnections, newNodes, newConnections)
    if (!newId) continue
    const newPath = mindMapAdornmentPathKey(newId, newConnections)
    if (!newPath) continue
    next[newPath] = adornment
  }
  return next
}
