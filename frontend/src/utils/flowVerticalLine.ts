/**
 * Flow-map substep trunks are drawn center to center, so the stroke runs through
 * every node on the column. Filled pills cover that. Underline nodes do not.
 * Drop the spans that sit inside a node and keep the gaps between them.
 */

export interface VerticalSpan {
  top: number
  bottom: number
}

export interface FlowLineNodeBox {
  position: { x: number; y: number }
  computedPosition?: { x: number; y: number }
  dimensions?: { width?: number; height?: number }
}

export function verticalSegmentsOutsideSpans(
  yStart: number,
  yEnd: number,
  spans: VerticalSpan[]
): Array<{ from: number; to: number }> {
  const start = Math.min(yStart, yEnd)
  const end = Math.max(yStart, yEnd)
  const cuts = spans
    .map((span) => ({
      top: Math.max(start, Math.min(span.top, span.bottom)),
      bottom: Math.min(end, Math.max(span.top, span.bottom)),
    }))
    .filter((span) => span.bottom - span.top > 0.5)
    .sort((left, right) => left.top - right.top)

  const merged: VerticalSpan[] = []
  for (const cut of cuts) {
    const last = merged[merged.length - 1]
    if (!last || cut.top > last.bottom) {
      merged.push({ top: cut.top, bottom: cut.bottom })
    } else {
      last.bottom = Math.max(last.bottom, cut.bottom)
    }
  }

  const parts: Array<{ from: number; to: number }> = []
  let cursor = start
  for (const cut of merged) {
    if (cut.top - cursor > 0.5) parts.push({ from: cursor, to: cut.top })
    cursor = Math.max(cursor, cut.bottom)
  }
  if (end - cursor > 0.5) parts.push({ from: cursor, to: end })
  return parts
}

export function nodeSpansCrossingVertical(
  nodes: FlowLineNodeBox[],
  x: number,
  y0: number,
  y1: number
): VerticalSpan[] {
  const top = Math.min(y0, y1)
  const bottom = Math.max(y0, y1)
  const spans: VerticalSpan[] = []
  for (const node of nodes) {
    const width = node.dimensions?.width ?? 0
    const height = node.dimensions?.height ?? 0
    if (width <= 0 || height <= 0) continue
    const origin = node.computedPosition ?? node.position
    const left = origin.x
    const right = origin.x + width
    const nodeTop = origin.y
    const nodeBottom = origin.y + height
    if (x <= left + 1 || x >= right - 1) continue
    if (nodeBottom <= top + 0.5 || nodeTop >= bottom - 0.5) continue
    spans.push({ top: nodeTop, bottom: nodeBottom })
  }
  return spans
}
