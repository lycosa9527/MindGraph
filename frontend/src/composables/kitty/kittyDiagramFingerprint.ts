/**
 * Pinia diagram content fingerprint for hub persist and desktop recovery.
 */
import { mindMapLiveSpecExtrasFingerprint } from '@/utils/mindMapLiveSpecExtras'

type DiagramDataLike = {
  nodes?: unknown[]
  connections?: unknown[]
  _node_styles?: unknown
  _mindmap_theme?: unknown
  _mindmap_diagram_style?: unknown
  _mindmap_canvas?: unknown
  _collapsed_paths?: unknown
} | null

interface NodeLike {
  id?: string
  text?: string
  data?: { label?: string; mindMapUid?: string }
}

export function getKittyDiagramContentFingerprint(data: DiagramDataLike): string {
  if (!data) {
    return ''
  }
  const nodes = data.nodes ?? []
  const conns = data.connections ?? []
  const nodeContent = (n: unknown) => {
    const node = n as NodeLike
    return JSON.stringify({
      id: node.id,
      text: node.text ?? node.data?.label ?? '',
      // First layout assigns mindMapUid without text changes — must republish.
      mindMapUid: node.data?.mindMapUid ?? '',
    })
  }
  const connContent = (c: unknown) => JSON.stringify(c)
  return JSON.stringify({
    nodes: nodes.map(nodeContent).sort(),
    conns: conns.map(connContent).sort(),
    // Style/collapse-only edits must republish live_spec for mobile hydrate.
    mindMapExtras: mindMapLiveSpecExtrasFingerprint(data as Record<string, unknown>),
  })
}

/** Fingerprint voice-shaped diagram_data (children/topic) for live_context comparison. */
export function getKittyVoiceDiagramFingerprint(
  diagramData: Record<string, unknown> | null | undefined
): string {
  if (!diagramData || typeof diagramData !== 'object') {
    return ''
  }
  const children = diagramData.children
  if (Array.isArray(children)) {
    return JSON.stringify(
      children.map((c) =>
        typeof c === 'object' && c !== null ? JSON.stringify(c) : JSON.stringify(String(c))
      )
    )
  }
  return JSON.stringify({
    topic: diagramData.topic ?? '',
    center: diagramData.center ?? null,
    left: diagramData.left ?? '',
    right: diagramData.right ?? '',
  })
}
