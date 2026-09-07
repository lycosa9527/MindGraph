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

/** Merge theme defaults, persisted `_node_styles`, then inline `node.style`. */
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
  return selectedIds.filter((id) => !sources.has(id))
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
