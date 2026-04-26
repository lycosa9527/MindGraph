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
  return routePath === CANVAS_EDITOR_PATH_MOBILE
    ? CANVAS_EDITOR_PATH_MOBILE
    : CANVAS_EDITOR_PATH_DESKTOP
}

/** Landing-page `.mg` import: open editor on desktop or mobile canvas. */
export function canvasPathForImportNavigation(routePath: string): '/canvas' | '/m/canvas' {
  if (routePath === CANVAS_EDITOR_PATH_MOBILE || routePath.startsWith('/m/')) {
    return CANVAS_EDITOR_PATH_MOBILE
  }
  return CANVAS_EDITOR_PATH_DESKTOP
}
