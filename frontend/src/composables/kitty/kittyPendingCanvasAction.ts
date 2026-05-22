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
    if (parsed.kind === 'inline_recommendations' || parsed.kind === 'add_node_with_recommendations') {
      return parsed
    }
    return null
  } catch {
    return null
  }
}
