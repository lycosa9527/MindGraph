import { eventBus } from '@/composables/core/useEventBus'

let initialized = false
let openInlineEditCount = 0
let enterGuardFrames = 0
/** Node that just finished inline edit; next Enter sibling add should anchor here. */
let mindMapPostEditSiblingAnchor: string | null = null

/** Subscribe once — tracks open inline editors for canvas Enter routing. */
export function initInlineEditEnterGuard(): void {
  if (initialized) return
  initialized = true
  eventBus.on('node_editor:opening', () => {
    openInlineEditCount += 1
  })
  eventBus.on('node_editor:closed', () => {
    openInlineEditCount = Math.max(0, openInlineEditCount - 1)
    armInlineEditEnterGuard()
  })
  eventBus.on('canvas:pane_clicked', () => {
    clearMindMapPostEditSiblingAnchor()
  })
}

/** Remember which branch was just committed so Enter can add a sibling below it. */
export function setMindMapPostEditSiblingAnchor(nodeId: string | null): void {
  if (!nodeId || nodeId === 'topic') {
    mindMapPostEditSiblingAnchor = null
    return
  }
  mindMapPostEditSiblingAnchor = nodeId
}

export function clearMindMapPostEditSiblingAnchor(): void {
  mindMapPostEditSiblingAnchor = null
}

/** Prefer the node that just finished inline edit over stale diagram selection. */
export function consumeMindMapPostEditSiblingAnchor(
  fallbackSelectedId: string | undefined
): string | null {
  const anchor = mindMapPostEditSiblingAnchor
  mindMapPostEditSiblingAnchor = null
  if (anchor && anchor !== 'topic') return anchor
  if (fallbackSelectedId && fallbackSelectedId !== 'topic') return fallbackSelectedId
  return null
}

/** Block canvas-level Enter until the next animation frame after inline edit commits. */
export function armInlineEditEnterGuard(): void {
  enterGuardFrames = 2
  requestAnimationFrame(() => {
    enterGuardFrames = Math.max(0, enterGuardFrames - 1)
    if (enterGuardFrames > 0) {
      requestAnimationFrame(() => {
        enterGuardFrames = 0
      })
    }
  })
}

export function isInlineEditEnterGuarded(): boolean {
  return enterGuardFrames > 0
}

export function isInlineDiagramEditOpen(): boolean {
  return openInlineEditCount > 0
}

export function isInlineDiagramEditDomActive(): boolean {
  return document.querySelector('.inline-edit-wrapper') !== null
}

export function isInlineDiagramEditKeyEvent(event: KeyboardEvent): boolean {
  const target = event.target
  if (!(target instanceof HTMLElement)) return false
  return !!target.closest('.inline-edit-input, .inline-edit-wrapper, .inline-editable-text')
}

export function shouldBlockCanvasEnterShortcut(event: KeyboardEvent): boolean {
  if (event.isComposing || event.keyCode === 229) return true
  if (isInlineEditEnterGuarded()) return true
  if (isInlineDiagramEditOpen()) return true
  if (isInlineDiagramEditDomActive()) return true
  if (isInlineDiagramEditKeyEvent(event)) return true
  return false
}

/** @deprecated Use initInlineEditEnterGuard / armInlineEditEnterGuard */
export const armMindMapCanvasEnterGuard = armInlineEditEnterGuard
/** @deprecated Use isInlineEditEnterGuarded */
export const isMindMapCanvasEnterGuarded = isInlineEditEnterGuarded
