/**
 * Copy the LLM secondary mirror onto mind-map branch objects before layout.
 * Layout then copies `textSecondary` onto each node.
 */
import { mirrorRecordList, mirrorString, readSecondaryMirror } from './mirror'

function stampBranchList(nodes: unknown, secondaryNodes: Record<string, unknown>[]): void {
  if (!Array.isArray(nodes) || secondaryNodes.length !== nodes.length) return
  nodes.forEach((node, index) => {
    if (!node || typeof node !== 'object') return
    const branch = node as { textSecondary?: string; children?: unknown }
    const secondary = secondaryNodes[index]
    if (!secondary) return
    const text = mirrorString(secondary, 'text') ?? mirrorString(secondary, 'label')
    if (text) branch.textSecondary = text
    stampBranchList(branch.children, mirrorRecordList(secondary, 'children'))
  })
}

/** Mutates branch objects on the spec so the existing loader can read `textSecondary`. */
export function stampMindMapSecondary(spec: Record<string, unknown>): string | undefined {
  const mirror = readSecondaryMirror(spec)
  if (!mirror) return undefined
  stampBranchList(spec.children, mirrorRecordList(mirror, 'children'))
  return mirrorString(mirror, 'topic')
}
