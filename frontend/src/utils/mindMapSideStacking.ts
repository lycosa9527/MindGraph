/**
 * Symmetric vertical stacking for first-level mind-map branches on one side.
 * Two branches mirror around topic center; 3+ chain sequentially with tight gaps.
 */
export function computeSymmetricRootStartYs(
  subtreeSpans: number[],
  topicCenterY: number,
  crossBranchGap: number
): number[] {
  const n = subtreeSpans.length
  if (n === 0) return []

  if (n === 1) {
    return [topicCenterY - subtreeSpans[0] / 2]
  }

  if (n === 2) {
    const [h0, h1] = subtreeSpans
    const offset = crossBranchGap / 2 + Math.max(h0, h1) / 2
    return [topicCenterY - offset - h0 / 2, topicCenterY + offset - h1 / 2]
  }

  const totalHeight =
    subtreeSpans.reduce((a, b) => a + b, 0) + (n - 1) * crossBranchGap
  let y = topicCenterY - totalHeight / 2
  return subtreeSpans.map((span) => {
    const start = y
    y += span + crossBranchGap
    return start
  })
}
