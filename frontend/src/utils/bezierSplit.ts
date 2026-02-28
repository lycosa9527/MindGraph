/**
 * Bezier path splitting utility for concept map arrowhead segments.
 * Splits a cubic bezier path at t=0.5 using De Casteljau's algorithm.
 */

interface Point {
  x: number
  y: number
}

function lerp(a: Point, b: Point, t: number): Point {
  return {
    x: a.x + (b.x - a.x) * t,
    y: a.y + (b.y - a.y) * t,
  }
}

/**
 * Parse cubic bezier path string (format: M x,y C cx1,cy1 cx2,cy2 x,y)
 * Returns control points [p0, p1, p2, p3] or null if parse fails.
 */
export function parseCubicBezierPath(path: string): [Point, Point, Point, Point] | null {
  const match = path.match(
    /M([\d.-]+),([\d.-]+)\s+C([\d.-]+),([\d.-]+)\s+([\d.-]+),([\d.-]+)\s+([\d.-]+),([\d.-]+)/
  )
  if (!match) return null

  const [, x0, y0, x1, y1, x2, y2, x3, y3] = match.map(Number)
  return [
    { x: x0, y: y0 },
    { x: x1, y: y1 },
    { x: x2, y: y2 },
    { x: x3, y: y3 },
  ]
}

/**
 * Split cubic bezier at parameter t using De Casteljau's algorithm.
 * Returns [firstSegmentPath, secondSegmentPath] as SVG path strings.
 */
export function splitCubicBezierAt(
  p0: Point,
  p1: Point,
  p2: Point,
  p3: Point,
  t: number
): [string, string] {
  const p11 = lerp(p0, p1, t)
  const p21 = lerp(p1, p2, t)
  const p31 = lerp(p2, p3, t)
  const p12 = lerp(p11, p21, t)
  const p22 = lerp(p21, p31, t)
  const p13 = lerp(p12, p22, t)

  const firstPath = `M${p0.x},${p0.y} C${p11.x},${p11.y} ${p12.x},${p12.y} ${p13.x},${p13.y}`
  const secondPath = `M${p13.x},${p13.y} C${p22.x},${p22.y} ${p31.x},${p31.y} ${p3.x},${p3.y}`

  return [firstPath, secondPath]
}

/**
 * Split a full cubic bezier path string at midpoint (t=0.5).
 * Returns { segment1, segment2 } or null if parse fails.
 */
export function splitBezierPathAtMidpoint(path: string): {
  segment1: string
  segment2: string
} | null {
  const points = parseCubicBezierPath(path)
  if (!points) return null

  const [segment1, segment2] = splitCubicBezierAt(
    points[0],
    points[1],
    points[2],
    points[3],
    0.5
  )

  return { segment1, segment2 }
}
