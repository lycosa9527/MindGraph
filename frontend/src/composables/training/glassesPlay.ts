/**
 * The order bubbles enter around a topic while a course slide opens.
 */

export type ClockPoint = { id: string; x: number; y: number }

export type ShownLink = { id: string; source: string; target: string }

/** Angle from the top of the circle, increasing clockwise on a screen. */
export function clockwiseFromTop(points: ClockPoint[], center: ClockPoint): string[] {
  const scored = points.map((point) => {
    const angle = Math.atan2(point.y - center.y, point.x - center.x)
    const fromTop = (angle + Math.PI / 2 + Math.PI * 2) % (Math.PI * 2)
    return { id: point.id, fromTop }
  })
  scored.sort((a, b) => a.fromTop - b.fromTop || a.id.localeCompare(b.id))
  return scored.map((row) => row.id)
}

export type DoubleBubbleRole = 'similarity' | 'leftDiff' | 'rightDiff'

/** Similarities first, then each difference row from the left topic to the right. */
export function doubleBubbleRevealOrder(
  nodes: { id: string; role: DoubleBubbleRole | null; index: number }[]
): { similarities: string[]; differences: string[] } {
  const byRow = (
    left: { id: string; role: DoubleBubbleRole | null; index: number },
    right: { id: string; role: DoubleBubbleRole | null; index: number }
  ) =>
    left.index - right.index ||
    sideRank(left.role) - sideRank(right.role) ||
    left.id.localeCompare(right.id)
  const similarities = nodes
    .filter((node) => node.role === 'similarity')
    .sort(byRow)
    .map((node) => node.id)
  const differences = nodes
    .filter((node) => node.role === 'leftDiff' || node.role === 'rightDiff')
    .sort(byRow)
    .map((node) => node.id)
  return { similarities, differences }
}

function sideRank(role: DoubleBubbleRole | null): number {
  if (role === 'leftDiff') return 0
  if (role === 'rightDiff') return 1
  return 2
}

/** Lines whose both ends are already on screen. */
export function linesBetweenShown(links: ShownLink[], shown: ReadonlySet<string>): string[] {
  return links
    .filter((link) => shown.has(link.source) && shown.has(link.target))
    .map((link) => link.id)
}
