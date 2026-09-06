/**
 * Stash canvas-only Kitty voice actions while the user is on `/m/kitty`.
 */
export type KittyPendingCanvasAction =
  | {
      kind: 'inline_recommendations'
      nodeId?: string
      nodeIndex?: number
    }
  | {
      kind: 'add_node_with_recommendations'
      text?: string
    }

const KITTY_PENDING_CANVAS_ACTION_KEY = 'mindgraph:kitty_pending_canvas_action'
const KITTY_PENDING_DESKTOP_EXPLAIN_KEY = 'mindgraph:kitty_pending_desktop_explain'

export function stashKittyPendingCanvasAction(action: KittyPendingCanvasAction): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  sessionStorage.setItem(KITTY_PENDING_CANVAS_ACTION_KEY, JSON.stringify(action))
}

export function consumeKittyPendingCanvasAction(): KittyPendingCanvasAction | null {
  if (typeof sessionStorage === 'undefined') {
    return null
  }
  const raw = sessionStorage.getItem(KITTY_PENDING_CANVAS_ACTION_KEY)
  if (!raw) {
    return null
  }
  sessionStorage.removeItem(KITTY_PENDING_CANVAS_ACTION_KEY)
  try {
    const parsed = JSON.parse(raw) as KittyPendingCanvasAction
    if (
      parsed.kind === 'inline_recommendations' ||
      parsed.kind === 'add_node_with_recommendations'
    ) {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

export type KittyPendingDesktopExplain = {
  nodeId: string
  libraryId?: string
}

function parsePendingDesktopExplain(raw: string): KittyPendingDesktopExplain | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }
  try {
    const parsed: unknown = JSON.parse(trimmed)
    if (typeof parsed === 'string') {
      const nodeId = parsed.trim()
      return nodeId !== '' ? { nodeId } : null
    }
    if (parsed == null || typeof parsed !== 'object') {
      return null
    }
    const rec = parsed as { nodeId?: unknown; libraryId?: unknown }
    const nodeId = typeof rec.nodeId === 'string' ? rec.nodeId.trim() : ''
    if (!nodeId) {
      return null
    }
    const libraryId = typeof rec.libraryId === 'string' ? rec.libraryId.trim() : ''
    return libraryId !== '' ? { nodeId, libraryId } : { nodeId }
  } catch {
    return { nodeId: trimmed }
  }
}

/** Desktop poll received explain_node before `/canvas` (or the target library) is mounted. */
export function stashKittyPendingDesktopExplain(nodeId: string, libraryId?: string): void {
  const id = nodeId.trim()
  if (!id || typeof sessionStorage === 'undefined') {
    return
  }
  const lib = libraryId?.trim() ?? ''
  const payload: KittyPendingDesktopExplain = lib !== '' ? { nodeId: id, libraryId: lib } : { nodeId: id }
  sessionStorage.setItem(KITTY_PENDING_DESKTOP_EXPLAIN_KEY, JSON.stringify(payload))
}

export function peekKittyPendingDesktopExplain(): KittyPendingDesktopExplain | null {
  if (typeof sessionStorage === 'undefined') {
    return null
  }
  const raw = sessionStorage.getItem(KITTY_PENDING_DESKTOP_EXPLAIN_KEY)
  if (!raw) {
    return null
  }
  return parsePendingDesktopExplain(raw)
}

export function consumeKittyPendingDesktopExplain(): KittyPendingDesktopExplain | null {
  const pending = peekKittyPendingDesktopExplain()
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(KITTY_PENDING_DESKTOP_EXPLAIN_KEY)
  }
  return pending
}

/** Flush only when the canvas node exists, has a label, and (if scoped) the library matches. */
export function shouldFlushKittyPendingDesktopExplain(
  pending: KittyPendingDesktopExplain | null,
  activeLibraryId: string | null | undefined,
  nodes: readonly { id: string; text?: string | null }[]
): string | null {
  if (!pending) {
    return null
  }
  if (pending.libraryId) {
    const active = activeLibraryId?.trim() ?? ''
    if (active !== pending.libraryId) {
      return null
    }
  }
  const node = nodes.find((row) => row.id === pending.nodeId)
  const label = (node?.text ?? '').trim()
  return label !== '' ? pending.nodeId : null
}
