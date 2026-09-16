/**
 * Rewrite leftover flow-map slot ids (`flow-step-0`) to stable UUIDs.
 * Topic stays ``flow-topic``. Already-stable ids are kept.
 */
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  FLOW_MAP_LEGACY_ID_DATA_KEY,
  FLOW_MAP_UID_DATA_KEY,
  FLOW_TOPIC_NODE_ID,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  isFlowMapTopicId,
  isLeftoverFlowMapId,
  parseLeftoverFlowStepIndex,
  parseLeftoverFlowSubstepRef,
  readFlowMapUid,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
  stampFlowMapStepData,
  stampFlowMapSubstepData,
  takeFlowMapStableId,
} from '@/utils/flowMapIdentity'

export type FlowMapIdentityIdMap = Record<string, string>

export type FlowMapIdentityMigrateResult = {
  nodes: DiagramNode[]
  connections: Connection[]
  idMap: FlowMapIdentityIdMap
  nodeStyles?: Record<string, NodeStyle>
}

function claimedIdentityIds(nodes: readonly DiagramNode[]): Set<string> {
  const claimed = new Set<string>([FLOW_TOPIC_NODE_ID])
  for (const node of nodes) {
    if (isLeftoverFlowMapId(node.id)) continue
    if (node.id) claimed.add(node.id)
    const uid = readFlowMapUid(node)
    if (uid) claimed.add(uid)
  }
  return claimed
}

function rewriteStyleKeys(
  styles: Record<string, NodeStyle> | undefined,
  idMap: FlowMapIdentityIdMap
): Record<string, NodeStyle> | undefined {
  if (!styles) return undefined
  const next: Record<string, NodeStyle> = {}
  for (const [key, value] of Object.entries(styles)) {
    next[idMap[key] ?? key] = value
  }
  return next
}

function rewriteEdgeId(edgeId: string, idMap: FlowMapIdentityIdMap): string {
  let next = edgeId
  for (const [oldId, newId] of Object.entries(idMap)) {
    if (next.includes(oldId)) {
      next = next.split(oldId).join(newId)
    }
  }
  return next
}

function parentFromConnections(
  nodeId: string,
  connections: Connection[],
  idMap: FlowMapIdentityIdMap
): string | null {
  const incoming = connections.find((connection) => connection.target === nodeId)
  if (!incoming) return null
  const source = idMap[incoming.source] ?? incoming.source
  return source === FLOW_TOPIC_NODE_ID ? null : source
}

function stampNode(
  node: DiagramNode,
  connections: Connection[],
  idMap: FlowMapIdentityIdMap
): DiagramNode {
  if (isFlowMapTopicId(node.id)) {
    return node
  }
  if (isFlowMapStepNode(node)) {
    const stepIndex = readFlowStepIndex(node)
    const index = stepIndex >= 0 ? stepIndex : 0
    return {
      ...node,
      data: {
        ...stampFlowMapStepData(index, node.data),
        [FLOW_MAP_UID_DATA_KEY]: node.id,
      },
    }
  }
  if (isFlowMapSubstepNode(node)) {
    const leftover = parseLeftoverFlowSubstepRef(node.id)
    const stepIndex = readFlowStepIndex(node)
    const subIndex = readFlowSubstepIndex(node)
    const parent =
      readFlowParentStepId(node) ?? parentFromConnections(node.id, connections, idMap) ?? ''
    return {
      ...node,
      data: {
        ...stampFlowMapSubstepData(
          stepIndex >= 0 ? stepIndex : (leftover?.stepIndex ?? 0),
          subIndex >= 0 ? subIndex : (leftover?.subIndex ?? 0),
          parent,
          node.data
        ),
        [FLOW_MAP_UID_DATA_KEY]: node.id,
      },
    }
  }
  return node
}

export function migrateFlowMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): FlowMapIdentityMigrateResult {
  const idMap: FlowMapIdentityIdMap = {}
  const claimed = claimedIdentityIds(nodes)
  let changed = false

  const nextNodes = nodes.map((node) => {
    if (isFlowMapTopicId(node.id) || !isLeftoverFlowMapId(node.id)) {
      return node
    }
    const identity = takeFlowMapStableId(claimed, readFlowMapUid(node))
    idMap[node.id] = identity
    changed = true
    const leftoverStep = parseLeftoverFlowStepIndex(node.id)
    const leftoverSub = parseLeftoverFlowSubstepRef(node.id)
    const baseData = {
      ...node.data,
      [FLOW_MAP_UID_DATA_KEY]: identity,
      [FLOW_MAP_LEGACY_ID_DATA_KEY]: node.id,
    }
    if (leftoverSub) {
      return {
        ...node,
        id: identity,
        data: stampFlowMapSubstepData(leftoverSub.stepIndex, leftoverSub.subIndex, '', baseData),
      }
    }
    return {
      ...node,
      id: identity,
      data: stampFlowMapStepData(leftoverStep >= 0 ? leftoverStep : 0, baseData),
    }
  })

  const nextConnections = changed
    ? connections.map((connection) => ({
        ...connection,
        source: idMap[connection.source] ?? connection.source,
        target: idMap[connection.target] ?? connection.target,
        id: rewriteEdgeId(connection.id, idMap),
      }))
    : connections

  const remapped = nextNodes.map((node) => {
    if (!isFlowMapSubstepNode(node)) return node
    const parent = readFlowParentStepId(node)
    if (parent && !isLeftoverFlowMapId(parent)) return node
    const leftoverParent = parent && isLeftoverFlowMapId(parent) ? idMap[parent] : undefined
    const fromEdge = parentFromConnections(node.id, nextConnections, idMap)
    const resolved = leftoverParent ?? fromEdge ?? parent ?? ''
    if (!resolved || resolved === parent) return node
    return {
      ...node,
      data: {
        ...node.data,
        parentStepId: resolved,
      },
    }
  })

  const stamped = remapped.map((node) => stampNode(node, nextConnections, idMap))
  return {
    nodes: stamped,
    connections: nextConnections,
    idMap,
    nodeStyles: changed ? rewriteStyleKeys(nodeStyles, idMap) : nodeStyles,
  }
}
