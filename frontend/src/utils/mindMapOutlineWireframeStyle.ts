import type { CSSProperties } from 'vue'

/** Printer ink — near-black for crisp B&W export. */
export const OUTLINE_WIREFRAME_INK = '#111827'

/** Connector stroke — slightly softer than node ink. */
export const OUTLINE_WIREFRAME_EDGE = '#374151'

/** Filled node background for outline export. */
export const OUTLINE_WIREFRAME_FILL = '#ffffff'

function normalizeBorderWidth(style: CSSProperties): string {
  const raw = style.borderWidth
  if (typeof raw === 'number') {
    return `${Math.max(raw, 1)}px`
  }
  if (typeof raw === 'string' && raw.trim()) {
    return raw
  }
  return '2px'
}

/**
 * Convert a rendered mind-map node box to printer-friendly outline styling:
 * white fill, black border/text, no shadows or theme fills.
 */
export function applyMindMapOutlineWireframeNodeStyle(
  style: CSSProperties,
  opts?: { isUnderline?: boolean }
): CSSProperties {
  const isUnderline = opts?.isUnderline === true
  const borderWidth = normalizeBorderWidth(style)

  if (isUnderline) {
    return {
      ...style,
      backgroundColor: 'transparent',
      backgroundImage: 'none',
      color: OUTLINE_WIREFRAME_INK,
      boxShadow: 'none',
    }
  }

  return {
    ...style,
    backgroundColor: OUTLINE_WIREFRAME_FILL,
    backgroundImage: 'none',
    backgroundClip: 'border-box',
    color: OUTLINE_WIREFRAME_INK,
    borderColor: OUTLINE_WIREFRAME_INK,
    borderStyle: 'solid',
    borderWidth,
    boxShadow: 'none',
  }
}

/** Underline bar beneath mind-map underline-shape nodes. */
export function applyMindMapOutlineWireframeUnderlineBar(style: CSSProperties): CSSProperties {
  return {
    ...style,
    backgroundColor: OUTLINE_WIREFRAME_INK,
    opacity: 1,
  }
}

export function resolveMindMapOutlineWireframeEdgeStroke(): string {
  return OUTLINE_WIREFRAME_EDGE
}
