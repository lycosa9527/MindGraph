/**
 * Stable identity for mind-map branches across tree rebuilds.
 * Layout ids (`branch-r-1-0`) are positional and change on move/reparent;
 * `data.mindMapUid` survives so styles/selection/dims can follow the node
 * even when multiple branches share the same label text.
 */
import { safeRandomUUID } from '@/utils/safeRandomUUID'
import type { DiagramNode } from '@/types'

export const MINDMAP_NODE_UID_DATA_KEY = 'mindMapUid'

export type MindMapBranchUidCarrier = {
  uid?: string
}

export function readMindMapNodeUid(
  node: Pick<DiagramNode, 'data'> | null | undefined
): string | null {
  const raw = node?.data?.[MINDMAP_NODE_UID_DATA_KEY]
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : null
}

/** Ensure a branch spec has a uid (mutates carrier when missing). */
export function ensureMindMapBranchUid(branch: MindMapBranchUidCarrier): string {
  const existing = typeof branch.uid === 'string' ? branch.uid.trim() : ''
  if (existing) {
    branch.uid = existing
    return existing
  }
  const uid = safeRandomUUID()
  branch.uid = uid
  return uid
}

export function findNodeIdByMindMapUid(
  nodes: DiagramNode[],
  uid: string
): string | null {
  for (const node of nodes) {
    if (!node.id.startsWith('branch-')) continue
    if (readMindMapNodeUid(node) === uid) return node.id
  }
  return null
}

/**
 * Before paste: keep uids that are absent from the live diagram (cut→paste),
 * otherwise mint fresh ones (copy→paste) so identities stay unique.
 */
export function rebindMindMapBranchUidsForPaste(
  branches: MindMapBranchUidCarrier[],
  existingUids: ReadonlySet<string>
): void {
  const claimed = new Set(existingUids)

  function walk(branch: MindMapBranchUidCarrier & { children?: MindMapBranchUidCarrier[] }): void {
    const current = typeof branch.uid === 'string' ? branch.uid.trim() : ''
    if (!current || claimed.has(current)) {
      branch.uid = safeRandomUUID()
    } else {
      branch.uid = current
    }
    claimed.add(branch.uid)
    const children = branch.children
    if (Array.isArray(children)) {
      children.forEach((child) => walk(child))
    }
  }

  branches.forEach((branch) => walk(branch))
}

export function collectMindMapNodeUids(nodes: DiagramNode[]): Set<string> {
  const uids = new Set<string>()
  for (const node of nodes) {
    const uid = readMindMapNodeUid(node)
    if (uid) uids.add(uid)
  }
  return uids
}
