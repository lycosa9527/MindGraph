/**
 * Mobile Kitty → desktop SPA action queue (library jump, 节点解释).
 */
export async function enqueueKittyDesktopAction(
  payload: Record<string, string>
): Promise<boolean> {
  try {
    const res = await fetch('/api/kitty/desktop_action/enqueue', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      return false
    }
    const data = (await res.json()) as { ok?: boolean }
    return data.ok === true
  } catch {
    return false
  }
}

/** Chip tap → desktop 节点解释. */
export async function enqueueKittyDesktopExplainNode(options: {
  nodeId: string
  nodeLabel?: string
  diagramLibraryId?: string
}): Promise<boolean> {
  const nodeId = options.nodeId.trim()
  if (!nodeId) {
    return false
  }
  const body: Record<string, string> = {
    kind: 'explain_node',
    node_id: nodeId,
  }
  const label = options.nodeLabel?.trim() ?? ''
  if (label) {
    body.node_label = label
  }
  const libraryId = options.diagramLibraryId?.trim() ?? ''
  if (libraryId) {
    body.diagram_library_id = libraryId
  }
  return enqueueKittyDesktopAction(body)
}
