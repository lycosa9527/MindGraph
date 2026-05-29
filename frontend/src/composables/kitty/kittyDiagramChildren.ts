/**
 * Pure Kitty diagram child indexing — shared by voice context, click wheel, and canvas actions.
 */
import { resolveVoiceNodeId } from '@/composables/editor/diagramVoiceMutations'
import type { DiagramNode, DiagramType } from '@/types'

export type KittyVoiceContextNode = {
  id: string
  text?: string
  type?: string
  data?: Record<string, unknown>
}

export function kittyNodeDisplayText(node: KittyVoiceContextNode): string {
  const raw = (node.text ?? '').trim()
  if (raw.length > 0) {
    return raw
  }
  const label = node.data?.label
  if (typeof label === 'string' && label.trim().length > 0) {
    return label.trim()
  }
  const alt = node.data?.text
  if (typeof alt === 'string') {
    return alt.trim()
  }
  return ''
}

/** Node list for backend indexing — excludes center/topic nodes. */
export function buildKittyChildren(
  dt: DiagramType,
  nodes: KittyVoiceContextNode[]
): Array<{ id: string; index: number; text: string }> {
  const toChild = (n: KittyVoiceContextNode, index: number) => ({
    id: n.id,
    index,
    text: kittyNodeDisplayText(n),
  })

  switch (dt) {
    case 'circle_map':
      return nodes
        .filter((n) => (n.type === 'bubble' || n.type === 'context') && n.id.startsWith('context-'))
        .map(toChild)
    case 'bubble_map':
      return nodes.filter((n) => n.type === 'bubble' || n.type === 'attribute').map(toChild)
    case 'flow_map':
      return nodes.filter((n) => n.id.startsWith('flow-step-')).map(toChild)
    case 'multi_flow_map':
      return nodes
        .filter((n) => n.id.startsWith('cause-') || n.id.startsWith('effect-'))
        .map(toChild)
    case 'double_bubble_map':
      return nodes
        .filter(
          (n) =>
            n.id.startsWith('similarity-') ||
            n.id.startsWith('left-diff-') ||
            n.id.startsWith('right-diff-')
        )
        .map(toChild)
    case 'brace_map':
      return nodes
        .filter((n) => n.id.startsWith('brace-part-') || n.id.startsWith('brace-subpart-'))
        .map(toChild)
    case 'bridge_map':
      return nodes.filter((n) => /^pair-\d+-left$/.test(n.id)).map(toChild)
    case 'tree_map':
      return nodes
        .filter((n) => n.id.startsWith('tree-cat-') || n.id.startsWith('tree-leaf-'))
        .map(toChild)
    case 'concept_map':
      return nodes.filter((n) => n.id.startsWith('concept-') && n.id !== 'topic').map(toChild)
    case 'mindmap':
    case 'mind_map':
      return nodes.filter((n) => n.id.startsWith('branch-')).map(toChild)
    default:
      return nodes
        .filter(
          (n) =>
            n.type !== 'topic' &&
            n.type !== 'center' &&
            n.type !== 'whole' &&
            ![
              'root',
              'topic',
              'center',
              'flow-topic',
              'event',
              'left-topic',
              'right-topic',
            ].includes(n.id)
        )
        .map(toChild)
  }
}

/** Resolve Kitty child node id from voice params (matches backend `children[]` indexing). */
export function resolveKittyChildNodeId(
  diagramType: DiagramType | null | undefined,
  nodes: KittyVoiceContextNode[],
  options: { nodeId?: string; nodeIndex?: number }
): string | undefined {
  if (typeof options.nodeId === 'string' && options.nodeId.length > 0) {
    return options.nodeId
  }
  if (options.nodeIndex === undefined) {
    return undefined
  }
  const dt = (diagramType ?? 'circle_map') as DiagramType
  const children = buildKittyChildren(dt, nodes)
  return children[options.nodeIndex]?.id
}

function normalizedDiagramKind(dt: DiagramType | null | undefined): string {
  if (!dt) {
    return 'circle_map'
  }
  return dt === 'mind_map' ? 'mindmap' : dt
}

/** Resolve selection ids from voice index, underscore ids, or Vue Flow ids. */
export function resolveKittySelectionNodeId(
  diagramType: DiagramType | null | undefined,
  nodes: KittyVoiceContextNode[],
  options: { nodeId?: string; nodeIndex?: number }
): string | undefined {
  const rawId = options.nodeId
  if (typeof rawId === 'string' && rawId.length > 0) {
    const kind = normalizedDiagramKind(diagramType)
    const resolved = resolveVoiceNodeId(kind, rawId, nodes as DiagramNode[])
    if (resolved) {
      return resolved
    }
    if (nodes.some((node) => node.id === rawId)) {
      return rawId
    }
  }
  return resolveKittyChildNodeId(diagramType, nodes, options)
}
