/**
 * Pinia diagram content fingerprint for hub persist and desktop recovery.
 */
type DiagramDataLike = { nodes?: unknown[]; connections?: unknown[] } | null

interface NodeLike {
  id?: string
  text?: string
  data?: { label?: string }
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
    })
  }
  const connContent = (c: unknown) => JSON.stringify(c)
  return JSON.stringify({
    nodes: nodes.map(nodeContent).sort(),
    conns: conns.map(connContent).sort(),
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
