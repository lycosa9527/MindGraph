/**
 * Mind map postcondition verification for Diagram Edit Tool (FE primary).
 */
import type { Connection, DiagramNode } from '@/types'

export type DiagramEditExpectedEffect = {
  op: string
  text?: string
  parent_ref?: string
  side?: string
  node_id?: string
  node_identifier?: string
  checks?: string[]
}

export type DiagramEditVerificationReport = {
  ok: boolean
  checks: string[]
  error?: string
}

export type DiagramFingerprint = {
  nodes: DiagramNode[]
  connections: Connection[]
}

export function normalizeDiagramText(value: unknown): string {
  if (typeof value !== 'string') return ''
  return value.trim().normalize('NFKC')
}

function nodeText(node: DiagramNode): string {
  const direct = node.text
  if (typeof direct === 'string' && direct.trim() !== '') {
    return normalizeDiagramText(direct)
  }
  const label = node.data?.label
  if (typeof label === 'string') {
    return normalizeDiagramText(label)
  }
  return ''
}

function topicNodes(nodes: DiagramNode[]): DiagramNode[] {
  return nodes.filter((n) => n.id === 'topic' || n.type === 'topic')
}

const THINKING_MAP_TYPES = new Set([
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
])

const RESERVED_ROOT_BY_TYPE: Record<string, string> = {
  circle_map: 'topic',
  bubble_map: 'topic',
  double_bubble_map: 'left-topic',
  tree_map: 'tree-topic',
  brace_map: 'brace-whole',
  flow_map: 'flow-topic',
  multi_flow_map: 'event',
  bridge_map: 'dimension-label',
}

function reservedRootNodes(nodes: DiagramNode[], diagramType: string): DiagramNode[] {
  const reserved = RESERVED_ROOT_BY_TYPE[diagramType] ?? 'topic'
  return nodes.filter(
    (node) =>
      node.id === reserved ||
      node.type === 'topic' ||
      node.type === 'center' ||
      node.type === 'whole' ||
      node.type === 'event'
  )
}

export function captureDiagramFingerprint(
  nodes: DiagramNode[],
  connections: Connection[]
): DiagramFingerprint {
  return {
    nodes: nodes.map((n) => ({ ...n })),
    connections: connections.map((c) => ({ ...c })),
  }
}

/**
 * Resolve canvas node ids created by an add mutation (diff before → after).
 * Prefers new nodes whose text matches ``effect.text`` when provided.
 */
export function resolveCreatedNodeIds(
  before: DiagramFingerprint,
  after: DiagramFingerprint,
  effect?: DiagramEditExpectedEffect
): string[] {
  const beforeIds = new Set(before.nodes.map((n) => n.id))
  const created = after.nodes.filter((n) => n.id && !beforeIds.has(n.id))
  if (created.length === 0) {
    return []
  }
  const want =
    effect?.text && effect.text.trim() !== ''
      ? normalizeDiagramText(effect.text)
      : ''
  if (want) {
    const matching = created.filter((n) => nodeText(n) === want)
    if (matching.length > 0) {
      return matching.map((n) => n.id)
    }
  }
  return created.map((n) => n.id)
}

export function verifyMindMapEffect(
  effect: DiagramEditExpectedEffect,
  fingerprint: DiagramFingerprint,
  beforeNodeCount?: number
): DiagramEditVerificationReport {
  const nodes = fingerprint.nodes
  const connections = fingerprint.connections
  const passed: string[] = []
  const failed: string[] = []

  const record = (check: string, ok: boolean): void => {
    if (ok) passed.push(check)
    else failed.push(check)
  }

  if (effect.op === 'update_center') {
    const topics = topicNodes(nodes)
    record('single_topic', topics.length === 1)
    if (effect.text && topics.length > 0) {
      record('topic_text_matches', nodeText(topics[0]) === normalizeDiagramText(effect.text))
    }
    return report(passed, failed)
  }

  if (effect.op === 'add_branch') {
    record('single_topic', topicNodes(nodes).length === 1)
    if (beforeNodeCount !== undefined) {
      record('delta_nodes', nodes.length === beforeNodeCount + 1)
    }
    if (effect.text) {
      const want = normalizeDiagramText(effect.text)
      const matches = nodes.filter((n) => nodeText(n) === want)
      record('node_exists', matches.length > 0)
      record('text_matches', matches.length > 0)
      if (matches.length > 0 && effect.parent_ref === 'topic') {
        const newId = matches[matches.length - 1].id
        const hasEdge = connections.some((c) => c.source === 'topic' && c.target === newId)
        record('parent_edge_exists', hasEdge)
      }
    }
    return report(passed, failed)
  }

  if (effect.op === 'add_child') {
    if (beforeNodeCount !== undefined) {
      record('delta_nodes', nodes.length === beforeNodeCount + 1)
    }
    if (effect.text) {
      const want = normalizeDiagramText(effect.text)
      const matches = nodes.filter((n) => nodeText(n) === want)
      record('node_exists', matches.length > 0)
      record('text_matches', matches.length > 0)
      if (matches.length > 0) {
        const newId = matches[matches.length - 1].id
        const parentRef = effect.parent_ref?.trim() ?? ''
        if (parentRef !== '' && parentRef !== 'topic') {
          const parentWant = normalizeDiagramText(parentRef)
          const parentNode = nodes.find(
            (n) => n.id === parentRef || nodeText(n) === parentWant
          )
          const parentId = parentNode?.id
          const hasParent = parentId
            ? connections.some((c) => c.source === parentId && c.target === newId)
            : false
          record('parent_edge_exists', hasParent)
        } else {
          const hasParent = connections.some((c) => c.target === newId)
          record('parent_edge_exists', hasParent)
        }
      }
    }
    return report(passed, failed)
  }

  if (effect.op === 'update_node') {
    if (beforeNodeCount !== undefined) {
      record('node_count_unchanged', nodes.length === beforeNodeCount)
    }
    const ident = (effect.node_identifier || effect.node_id || '').trim()
    if (ident) {
      const target = nodes.find((n) => n.id === ident)
      record('node_exists', Boolean(target))
      if (effect.text) {
        const want = normalizeDiagramText(effect.text)
        record('text_matches', target !== undefined && nodeText(target) === want)
      }
    } else if (effect.text) {
      const want = normalizeDiagramText(effect.text)
      const matches = nodes.filter((n) => nodeText(n) === want)
      record('text_matches', matches.length > 0)
      record('node_exists', matches.length > 0)
    }
    return report(passed, failed)
  }

  if (effect.op === 'delete_node') {
    if (effect.node_identifier) {
      const ident = normalizeDiagramText(effect.node_identifier)
      const absent = !nodes.some((n) => n.id === ident || nodeText(n) === ident)
      record('node_absent', absent)
    }
    const ids = new Set(nodes.map((n) => n.id))
    const dangling = connections.some(
      (c) => !ids.has(c.source) || !ids.has(c.target)
    )
    record('no_dangling_edges', !dangling)
    record('tree_rooted_at_topic', topicNodes(nodes).length === 1)
    return report(passed, failed)
  }

  return { ok: false, checks: [], error: 'unsupported_effect' }
}

function report(passed: string[], failed: string[]): DiagramEditVerificationReport {
  if (failed.length > 0) {
    return { ok: false, checks: passed, error: `failed: ${failed.join(', ')}` }
  }
  return { ok: true, checks: passed }
}

export function verifyThinkingMapEffect(
  effect: DiagramEditExpectedEffect,
  fingerprint: DiagramFingerprint,
  beforeNodeCount: number | undefined,
  diagramType: string
): DiagramEditVerificationReport {
  const nodes = fingerprint.nodes
  const connections = fingerprint.connections
  const passed: string[] = []
  const failed: string[] = []
  const record = (check: string, ok: boolean): void => {
    if (ok) passed.push(check)
    else failed.push(check)
  }
  const roots = reservedRootNodes(nodes, diagramType)

  if (effect.op === 'update_center') {
    record('reserved_root_present', roots.length >= 1)
    if (effect.text && roots.length > 0) {
      record('topic_text_matches', nodeText(roots[0]) === normalizeDiagramText(effect.text))
    }
    return report(passed, failed)
  }

  if (effect.op === 'add_branch' || effect.op === 'add_child') {
    record('reserved_root_present', roots.length >= 1)
    if (beforeNodeCount !== undefined) {
      record('delta_nodes', nodes.length === beforeNodeCount + 1)
    }
    if (effect.text) {
      const want = normalizeDiagramText(effect.text)
      const matches = nodes.filter((node) => nodeText(node) === want)
      record('node_exists', matches.length > 0)
      record('text_matches', matches.length > 0)
      if (matches.length > 0) {
        const newId = matches[matches.length - 1].id
        record(
          'parent_edge_exists',
          connections.some((connection) => connection.target === newId)
        )
      }
    }
    return report(passed, failed)
  }

  if (effect.op === 'update_node') {
    return verifyMindMapEffect(effect, fingerprint, beforeNodeCount)
  }

  if (effect.op === 'delete_node') {
    if (effect.node_identifier) {
      const ident = normalizeDiagramText(effect.node_identifier)
      const absent = !nodes.some((node) => node.id === ident || nodeText(node) === ident)
      record('node_absent', absent)
    }
    const ids = new Set(nodes.map((node) => node.id))
    const dangling = connections.some(
      (connection) => !ids.has(connection.source) || !ids.has(connection.target)
    )
    record('no_dangling_edges', !dangling)
    record('reserved_root_present', roots.length >= 1)
    return report(passed, failed)
  }

  return { ok: false, checks: [], error: 'unsupported_effect' }
}

export function verifyDiagramEffect(
  effect: DiagramEditExpectedEffect,
  fingerprint: DiagramFingerprint,
  beforeNodeCount: number | undefined,
  diagramType: string
): DiagramEditVerificationReport {
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return verifyMindMapEffect(effect, fingerprint, beforeNodeCount)
  }
  if (THINKING_MAP_TYPES.has(diagramType)) {
    return verifyThinkingMapEffect(effect, fingerprint, beforeNodeCount, diagramType)
  }
  return { ok: false, checks: [], error: 'unsupported_diagram_type' }
}
