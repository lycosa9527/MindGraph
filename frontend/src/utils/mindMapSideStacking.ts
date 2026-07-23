/**
 * Vertical stacking helpers for first-level mind-map branches on one side.
 * Multi-root sides pack sequentially with a uniform cross-branch gap (no n=2
 * special case — that inflated gaps when subtree spans differed).
 */
import type { DiagramNode } from '@/types'

import { readMindMapNodeUid } from '@/utils/mindMapNodeUid'

/** Topic-centered sequential start tops for one side's root subtrees. */
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

  const totalHeight =
    subtreeSpans.reduce((a, b) => a + b, 0) + (n - 1) * crossBranchGap
  let y = topicCenterY - totalHeight / 2
  return subtreeSpans.map((span) => {
    const start = y
    y += span + crossBranchGap
    return start
  })
}

/** Sequential start tops beginning at a fixed first-root top Y. */
export function computeSequentialRootStartYsFrom(
  startY: number,
  subtreeSpans: number[],
  crossBranchGap: number
): number[] {
  let y = startY
  return subtreeSpans.map((span) => {
    const start = y
    y += span + crossBranchGap
    return start
  })
}

/**
 * Translate every node on the anchor's side so the anchor keeps `anchorY`.
 * Used after sibling insert reload so Enter-below does not slide the selected branch.
 */
export function applyMindMapSideAnchorYPreserve(
  nodes: DiagramNode[],
  anchorUid: string,
  anchorY: number
): DiagramNode[] {
  const trimmedUid = anchorUid.trim()
  if (!trimmedUid) return nodes

  const anchor = nodes.find((node) => readMindMapNodeUid(node) === trimmedUid)
  if (!anchor?.position) return nodes

  const sidePrefix = anchor.id.startsWith('branch-l-')
    ? 'branch-l-'
    : anchor.id.startsWith('branch-r-')
      ? 'branch-r-'
      : null
  if (!sidePrefix) return nodes

  const delta = anchorY - anchor.position.y
  if (Math.abs(delta) < 0.5) return nodes

  return nodes.map((node) => {
    if (!node.position || !node.id.startsWith(sidePrefix)) return node
    return {
      ...node,
      position: { ...node.position, y: node.position.y + delta },
    }
  })
}
