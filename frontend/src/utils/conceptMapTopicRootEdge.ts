import {
  getAllRootConceptNodeTexts,
  getAllTopicRootRelationshipLabels,
  getConceptMapTopicRootRelationshipLabel,
} from '@/stores/diagram/diagramDefaultLabels'
import { registerLocaleLabelCacheInvalidator } from '@/i18n/localeLabelCache'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode } from '@/types'

let cachedRootLabelSet: Set<string> | null = null
let cachedRootNodeTextSet: Set<string> | null = null

function getRootLabelSet(): Set<string> {
  if (cachedRootLabelSet === null) {
    cachedRootLabelSet = new Set(getAllTopicRootRelationshipLabels())
  }
  return cachedRootLabelSet
}

function getRootNodeTextSet(): Set<string> {
  if (cachedRootNodeTextSet === null) {
    cachedRootNodeTextSet = new Set(getAllRootConceptNodeTexts())
  }
  return cachedRootNodeTextSet
}

function invalidateConceptMapTopicRootEdgeCaches(): void {
  cachedRootLabelSet = null
  cachedRootNodeTextSet = null
}

registerLocaleLabelCacheInvalidator(invalidateConceptMapTopicRootEdgeCaches)

/**
 * Target node id for the topic → root concept link (identified by fixed relationship label).
 */
export function getTopicRootConceptTargetId(
  connections: Connection[] | undefined | null
): string | null {
  if (!connections?.length) return null
  const rootLabels = getRootLabelSet()
  const c = connections.find(
    (x) => x.source === 'topic' && rootLabels.has((x.label ?? '').trim())
  )
  return c?.target ?? null
}

/**
 * True for the edge from topic (focus question) to the node whose text is the default root concept.
 */
export function isTopicToRootConceptConnection(
  conn: Pick<Connection, 'source' | 'target'>,
  nodes: DiagramNode[] | undefined | null
): boolean {
  if (conn.source !== 'topic' || !nodes?.length) return false
  const target = nodes.find((n) => n.id === conn.target)
  return getRootNodeTextSet().has((target?.text ?? '').trim())
}

export function normalizeTopicRootLabelIfNeeded(
  conn: Connection,
  nodes: DiagramNode[] | undefined | null
): void {
  if (!isTopicToRootConceptConnection(conn, nodes)) return
  conn.label = getConceptMapTopicRootRelationshipLabel(useUIStore().language)
}

export function normalizeAllConceptMapTopicRootLabels(
  connections: Connection[] | undefined,
  nodes: DiagramNode[] | undefined
): void {
  if (!connections?.length || !nodes?.length) return
  for (const c of connections) {
    normalizeTopicRootLabelIfNeeded(c, nodes)
  }
}
