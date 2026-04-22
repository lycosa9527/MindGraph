/**
 * Tracks which route opened the diagram canvas so "back" can use history.pop
 * when the user came from MindGraph (avoids duplicate /mindgraph stack entries).
 */
export const CANVAS_ENTRY_PATH_KEY = 'mindgraph_canvas_entry'

export const CANVAS_EDITOR_PATH_DESKTOP = '/canvas'
export const CANVAS_EDITOR_PATH_MOBILE = '/m/canvas'

export function isMindGraphLandingPath(path: string): boolean {
  return path === '/mindgraph' || path === '/m/mindgraph'
}

/** Use when replacing/pushing the editor URL so mobile stays on /m/canvas. */
export function canvasEditorPathForRoute(routePath: string): '/canvas' | '/m/canvas' {
  return routePath === CANVAS_EDITOR_PATH_MOBILE ? CANVAS_EDITOR_PATH_MOBILE : CANVAS_EDITOR_PATH_DESKTOP
}
