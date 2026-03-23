import {
  ALL_ROOT_CONCEPT_NODE_TEXTS,
  ALL_TOPIC_ROOT_RELATIONSHIP_LABELS,
  getConceptMapTopicRootRelationshipLabel,
} from '@/stores/diagram/diagramDefaultLabels'
import { useUIStore } from '@/stores/ui'
import type { Connection, DiagramNode } from '@/types'

const ROOT_LABEL_SET = new Set(ALL_TOPIC_ROOT_RELATIONSHIP_LABELS)
const ROOT_NODE_TEXT_SET = new Set(ALL_ROOT_CONCEPT_NODE_TEXTS)

/**
 * Target node id for the topic → root concept link (identified by fixed relationship label).
 */
export function getTopicRootConceptTargetId(
  connections: Connection[] | undefined | null
): string | null {
  if (!connections?.length) return null
  const c = connections.find(
    (x) => x.source === 'topic' && ROOT_LABEL_SET.has((x.label ?? '').trim())
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
  return ROOT_NODE_TEXT_SET.has((target?.text ?? '').trim())
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
