/**
 * Shared decision + confirm for opening a library diagram on the canvas
 * (MindMate «Edit in canvas», Kitty open_library_diagram).
 */
import { loadElMessageBox } from '@/composables/core/notifications'

export type CanvasLibraryOpenDecision = 'noop' | 'confirm' | 'navigate'

/** True when the current route is the diagram editor (desktop or mobile). */
export function isCanvasEditorRoutePath(routePath: string): boolean {
  return (
    routePath === '/canvas' ||
    routePath === '/m/canvas' ||
    routePath.startsWith('/canvas/') ||
    routePath.startsWith('/m/canvas/')
  )
}

/**
 * Decide whether opening `targetDiagramId` should no-op, confirm, or navigate.
 * Confirm when already on canvas with a different active library diagram.
 */
export function decideCanvasLibraryDiagramOpen(
  routePath: string,
  currentDiagramId: string | null | undefined,
  targetDiagramId: string
): CanvasLibraryOpenDecision {
  const target = targetDiagramId.trim()
  if (!target) {
    return 'noop'
  }
  const onCanvas = isCanvasEditorRoutePath(routePath)
  const current = currentDiagramId?.trim() ?? ''
  if (onCanvas && current === target) {
    return 'noop'
  }
  if (onCanvas && current.length > 0 && current !== target) {
    return 'confirm'
  }
  return 'navigate'
}

export async function confirmCanvasLibraryDiagramOpen(options: {
  title: string
  message: string
  confirmButtonText: string
  cancelButtonText: string
}): Promise<boolean> {
  try {
    const ElMessageBox = await loadElMessageBox()
    await ElMessageBox.confirm(options.message, options.title, {
      confirmButtonText: options.confirmButtonText,
      cancelButtonText: options.cancelButtonText,
      type: 'warning',
      distinguishCancelAndClose: true,
    })
    return true
  } catch {
    return false
  }
}
