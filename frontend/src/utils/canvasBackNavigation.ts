/**
 * Tracks which route opened the diagram canvas so "back" can return there in one step
 * (without relying on browser history depth — prompt-to-diagram often stacks
 * /canvas then /canvas?diagramId=…).
 */
import type { Router } from 'vue-router'

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

/** Default MindGraph landing when canvas entry path is unknown. */
export function defaultMindGraphLandingPath(routePath: string): '/mindgraph' | '/m/mindgraph' {
  return routePath === CANVAS_EDITOR_PATH_MOBILE || routePath.startsWith('/m/')
    ? '/m/mindgraph'
    : '/mindgraph'
}

/**
 * Leave the canvas editor in one click.
 * Uses replace (not history.back) so extra canvas stack entries from auto-save do not
 * require multiple back clicks.
 */
export function navigateBackFromCanvas(router: Router, currentRoutePath: string): void {
  const entry = sessionStorage.getItem(CANVAS_ENTRY_PATH_KEY)
  if (entry && isMindGraphLandingPath(entry)) {
    void router.replace({ path: entry })
    return
  }
  void router.replace({ path: defaultMindGraphLandingPath(currentRoutePath) })
}
