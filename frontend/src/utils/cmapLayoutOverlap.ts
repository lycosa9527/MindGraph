/** Axis-aligned rects with top-left origin (MindGraph Vue Flow semantics). */

export interface TopLeftSizedRect {
  key: string
  x: number
  y: number
  width: number
  height: number
}

function intervalOverlap1D(aLo: number, aHi: number, bLo: number, bHi: number): number {
  const left = Math.max(aLo, bLo)
  const right = Math.min(aHi, bHi)
  return right - left
}

export function rectsTouchWithGapExclusive(
  a: TopLeftSizedRect,
  b: TopLeftSizedRect,
  gapPx: number
): boolean {
  const ax = a.x
  const ay = a.y
  const bx = b.x
  const by = b.y
  return !(
    ax + a.width + gapPx <= bx ||
    bx + b.width + gapPx <= ax ||
    ay + a.height + gapPx <= by ||
    by + b.height + gapPx <= ay
  )
}

/** Shortest MTV axis depth for overlaps (exclusive of gap hull). */

function penetrationDepth(
  a: TopLeftSizedRect,
  b: TopLeftSizedRect
): { axis: 'x' | 'y'; depth: number } | null {
  const ox = intervalOverlap1D(a.x, a.x + a.width, b.x, b.x + b.width)
  const oy = intervalOverlap1D(a.y, a.y + a.height, b.y, b.y + b.height)
  if (ox <= 0 || oy <= 0) {
    return null
  }

  const axis = ox < oy ? 'x' : 'y'

  const depth = Math.min(ox, oy)

  return { axis, depth }
}

/** Count unordered overlapping pairs (+ outer gap hull). */

export function countOverlappingRects(rects: TopLeftSizedRect[], gapPx = 2): number {
  let n = 0
  for (let i = 0; i < rects.length; i += 1) {
    const a = rects[i]
    if (!a) continue
    for (let j = i + 1; j < rects.length; j += 1) {
      const b = rects[j]
      if (!b) continue
      if (rectsTouchWithGapExclusive(a, b, gapPx)) {
        n += 1
      }
    }
  }
  return n
}

interface LayoutAnchor {
  x: number
  y: number
}

/**
 * Lightweight overlap projection preserving topology with weak anchor pullback.
 */

export function relaxTopLeftPillLayoutsEstimated(
  positions: Record<string, { x: number; y: number }>,
  sizeByKey: Record<string, { width: number; height: number }>,
  anchorByKey: Record<string, LayoutAnchor>,
  iterations = 24,
  gapPx = 4,
  anchorWeight = 0.085
): Record<string, { x: number; y: number }> {
  const keys = Object.keys(positions)
  if (keys.length === 0) return { ...positions }
  let current: Record<string, { x: number; y: number }> = { ...positions }

  function buildRects(): TopLeftSizedRect[] {
    return keys.map((key) => {
      const p = current[key]
      const s = sizeByKey[key] ?? { width: 140, height: 50 }
      return {
        key,
        x: p?.x ?? 0,
        y: p?.y ?? 0,
        width: Math.max(s.width, 42),
        height: Math.max(s.height, 32),
      }
    })
  }

  for (let it = 0; it < iterations; it += 1) {
    const rects = buildRects()
    const deltas = new Map<string, { dx: number; dy: number }>()
    keys.forEach((k) => deltas.set(k, { dx: 0, dy: 0 }))

    let hadOverlapThisRound = false

    for (let i = 0; i < rects.length; i += 1) {
      const ai = rects[i]
      if (!ai) continue
      for (let j = i + 1; j < rects.length; j += 1) {
        const bj = rects[j]
        if (!bj) continue
        if (!rectsTouchWithGapExclusive(ai, bj, gapPx)) continue

        hadOverlapThisRound = true

        const mtv = penetrationDepth(ai, bj)
        if (!mtv) continue

        const push = Math.max(mtv.depth / 2 + gapPx / 2, 4)

        const cxA = ai.x + ai.width / 2
        const cyA = ai.y + ai.height / 2
        const cxB = bj.x + bj.width / 2
        const cyB = bj.y + bj.height / 2

        let ux = cxB - cxA
        let uy = cyB - cyA
        if (mtv.axis === 'x') {
          uy = 0
          ux = ux < 0 ? -1 : 1
          if (ux === 0) ux = cxA <= cxB ? -1 : 1
        } else {
          ux = 0
          uy = uy < 0 ? -1 : 1
          if (uy === 0) uy = cyA <= cyB ? -1 : 1
        }

        const di = deltas.get(ai.key)
        const dj = deltas.get(bj.key)
        if (!di || !dj) continue

        di.dx -= ux * push

        di.dy -= uy * push

        dj.dx += ux * push

        dj.dy += uy * push
      }
    }

    if (!hadOverlapThisRound && it > 6) break

    const next: Record<string, { x: number; y: number }> = {}
    for (const k of keys) {
      const prev = current[k]

      const anc = anchorByKey[k]

      const dpos = deltas.get(k) ?? { dx: 0, dy: 0 }

      let nx = (prev?.x ?? 0) + dpos.dx
      let ny = (prev?.y ?? 0) + dpos.dy
      if (anc && Number.isFinite(anc.x)) {
        nx += anchorWeight * (anc.x - nx)
      }
      if (anc && Number.isFinite(anc.y)) {
        ny += anchorWeight * (anc.y - ny)
      }
      next[k] = { x: nx, y: ny }
    }
    current = next
  }

  return current
}
