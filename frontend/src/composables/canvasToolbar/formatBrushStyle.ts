import type { NodeStyle } from '@/types'

export const FORMAT_BRUSH_KEYS = [
  'backgroundColor',
  'borderColor',
  'textColor',
  'fontSize',
  'fontFamily',
  'fontWeight',
  'fontStyle',
  'textDecoration',
  'textAlign',
  'borderWidth',
  'borderStyle',
  'borderRadius',
  'nodeShape',
  'accentBarWidth',
  'accentBarColor',
] as const satisfies ReadonlyArray<keyof NodeStyle>

export function pickFormatBrushStyle(style: NodeStyle | Partial<NodeStyle> | undefined): NodeStyle {
  const copied: NodeStyle = {}
  if (!style) return copied
  for (const key of FORMAT_BRUSH_KEYS) {
    const value = style[key]
    if (value !== undefined) {
      ;(copied as Record<string, unknown>)[key] = value
    }
  }
  return copied
}

const NODE_STYLE_LAYOUT_KEYS = ['width', 'height', 'size'] as const

/** Drop leftover layout sizes from inline `node.style` without touching format keys. */
export function omitNodeStyleLayoutSizes(style: NodeStyle | undefined): NodeStyle | undefined {
  if (!style) return undefined
  if (NODE_STYLE_LAYOUT_KEYS.every((key) => style[key] === undefined)) return style
  const next: NodeStyle = { ...style }
  for (const key of NODE_STYLE_LAYOUT_KEYS) {
    delete next[key]
  }
  return next
}

/** Drop layout leftovers (`width` / `height` / `size`) from persisted `_node_styles`. */
export function sanitizePersistedNodeStylesRecord(
  styles: Record<string, NodeStyle> | null | undefined
): Record<string, NodeStyle> | undefined {
  if (!styles) return undefined
  const next: Record<string, NodeStyle> = {}
  for (const [nodeId, style] of Object.entries(styles)) {
    const cleaned = pickFormatBrushStyle(style)
    if (Object.keys(cleaned).length > 0) next[nodeId] = cleaned
  }
  return Object.keys(next).length > 0 ? next : undefined
}

export function collectFormatBrushStyle(
  inlineStyle: NodeStyle | undefined,
  persistedStyle: NodeStyle | undefined,
  themeFallback?: Partial<NodeStyle>
): NodeStyle {
  return pickFormatBrushStyle({
    ...themeFallback,
    ...persistedStyle,
    ...inlineStyle,
  })
}

export function formatBrushTargetsFromSelection(
  selectedIds: readonly string[],
  sourceIds: readonly string[]
): string[] {
  const sources = new Set(sourceIds)
  return selectedIds.filter((id) => Boolean(id) && !sources.has(id))
}

/** Windows-like double-click window so the second painter click locks instead of cancelling. */
export const FORMAT_BRUSH_DOUBLE_CLICK_MS = 500

export type FormatPainterClickAction = 'activate' | 'lock' | 'cancel' | 'noop'

/** Word: click = one-shot; double-click = keep applying until Esc / painter click. */
export function resolveFormatPainterClick(input: {
  active: boolean
  locked: boolean
  lockRequested: boolean
  elapsedMs: number
  doubleClickMs?: number
}): FormatPainterClickAction {
  const windowMs = input.doubleClickMs ?? FORMAT_BRUSH_DOUBLE_CLICK_MS
  if (input.lockRequested) {
    return input.locked ? 'noop' : 'lock'
  }
  if (!input.active) return 'activate'
  if (!input.locked && input.elapsedMs <= windowMs) return 'lock'
  return 'cancel'
}
