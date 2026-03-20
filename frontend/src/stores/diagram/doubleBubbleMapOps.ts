import type { DiagramContext } from './types'

export function useDoubleBubbleMapOpsSlice(ctx: DiagramContext) {
  function addDoubleBubbleMapNode(
    group: 'similarity' | 'leftDiff' | 'rightDiff',
    defaultText: string,
    pairText?: string
  ): boolean {
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return false

    const similarities = (spec.similarities as string[]) || []
    const leftDifferences = (spec.leftDifferences as string[]) || []
    const rightDifferences = (spec.rightDifferences as string[]) || []

    if (group === 'similarity') {
      spec.similarities = [...similarities, defaultText]
    } else {
      spec.leftDifferences = [...leftDifferences, defaultText]
      spec.rightDifferences = [...rightDifferences, pairText ?? defaultText]
    }

    return ctx.loadFromSpec(spec, 'double_bubble_map')
  }

  function removeDoubleBubbleMapNodes(nodeIds: string[]): number {
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return 0

    const simIndices = new Set(
      nodeIds
        .filter((id) => /^similarity-\d+$/.test(id))
        .map((id) => parseInt(id.replace('similarity-', ''), 10))
    )
    const leftDiffIndices = new Set(
      nodeIds
        .filter((id) => /^left-diff-\d+$/.test(id))
        .map((id) => parseInt(id.replace('left-diff-', ''), 10))
    )
    const rightDiffIndices = new Set(
      nodeIds
        .filter((id) => /^right-diff-\d+$/.test(id))
        .map((id) => parseInt(id.replace('right-diff-', ''), 10))
    )

    const similarities = ((spec.similarities as string[]) || []).filter(
      (_, i) => !simIndices.has(i)
    )
    const leftDifferences = ((spec.leftDifferences as string[]) || []).filter(
      (_, i) => !leftDiffIndices.has(i)
    )
    const rightDifferences = ((spec.rightDifferences as string[]) || []).filter(
      (_, i) => !rightDiffIndices.has(i)
    )

    spec.similarities = similarities
    spec.leftDifferences = leftDifferences
    spec.rightDifferences = rightDifferences

    ctx.loadFromSpec(spec, 'double_bubble_map')
    return simIndices.size + leftDiffIndices.size + rightDiffIndices.size
  }

  return { addDoubleBubbleMapNode, removeDoubleBubbleMapNodes }
}
