import { eventBus } from '@/composables/core/useEventBus'
import { markMindMapInlineEditStage } from '@/utils/mindMapInlineEditDebug'

let initialized = false
/** Node ids with an open inline editor (opening without matching closed = zombie). */
const openInlineEditNodeIds = new Set<string>()
let enterGuardFrames = 0
/** Node that just finished inline edit; next Enter sibling add should anchor here. */
let mindMapPostEditSiblingAnchor: string | null = null

/** Subscribe once — tracks open inline editors for canvas Enter routing. */
export function initInlineEditEnterGuard(): void {
  if (initialized) return
  initialized = true
  eventBus.on('node_editor:opening', (payload) => {
    const nodeId = payload?.nodeId
    if (nodeId) {
      openInlineEditNodeIds.add(nodeId)
      return
    }
    // Legacy emitters without nodeId — keep a sentinel so Enter still blocks.
    openInlineEditNodeIds.add('__anonymous__')
  })
  eventBus.on('node_editor:closed', (payload) => {
    const nodeId = payload?.nodeId
    if (nodeId) {
      openInlineEditNodeIds.delete(nodeId)
    } else {
      openInlineEditNodeIds.delete('__anonymous__')
    }
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

/**
 * Resolve Enter sibling anchor.
 * - If the user selected a different node after editing, honor that selection
 *   (otherwise left-side post-edit anchors stole Enter from a right selection).
 * - If selection is empty/topic, fall back to the node that just finished edit.
 * - If selection matches the post-edit node, either is fine.
 */
export function consumeMindMapPostEditSiblingAnchor(
  fallbackSelectedId: string | undefined
): string | null {
  const anchor = mindMapPostEditSiblingAnchor
  mindMapPostEditSiblingAnchor = null
  const selected = fallbackSelectedId && fallbackSelectedId !== 'topic' ? fallbackSelectedId : null
  const postEdit = anchor && anchor !== 'topic' ? anchor : null

  if (selected && postEdit && selected !== postEdit) {
    return selected
  }
  if (postEdit) return postEdit
  return selected
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
  return openInlineEditNodeIds.size > 0
}

export function isInlineDiagramEditDomActive(): boolean {
  return document.querySelector('.inline-edit-wrapper') !== null
}

/**
 * Drop zombie open-edit ownership when the bus says editing but no editor DOM
 * exists (unmount / force-kill without node_editor:closed).
 */
export function reconcileOpenInlineEditorsWithDom(): void {
  if (openInlineEditNodeIds.size === 0) return
  if (isInlineDiagramEditDomActive()) return
  const focusedInput = document.activeElement
  if (
    focusedInput instanceof HTMLElement &&
    focusedInput.closest('.inline-edit-input, .inline-edit-wrapper')
  ) {
    return
  }
  const zombieIds = [...openInlineEditNodeIds]
  openInlineEditNodeIds.clear()
  markMindMapInlineEditStage('enter-guard:zombie-heal', {
    reason: 'open-set-without-editor-dom',
    zombieIds,
  })
}

export function isInlineDiagramEditKeyEvent(event: KeyboardEvent): boolean {
  const target = event.target
  if (!(target instanceof HTMLElement)) return false
  return !!target.closest('.inline-edit-input, .inline-edit-wrapper, .inline-editable-text')
}

export function shouldBlockCanvasEnterShortcut(event: KeyboardEvent): boolean {
  if (event.isComposing || event.keyCode === 229) return true
  if (isInlineEditEnterGuarded()) return true
  reconcileOpenInlineEditorsWithDom()
  if (isInlineDiagramEditOpen()) return true
  if (isInlineDiagramEditDomActive()) return true
  if (isInlineDiagramEditKeyEvent(event)) return true
  return false
}

/** @deprecated Use initInlineEditEnterGuard / armInlineEditEnterGuard */
export const armMindMapCanvasEnterGuard = armInlineEditEnterGuard
/** @deprecated Use isInlineEditEnterGuarded */
export const isMindMapCanvasEnterGuarded = isInlineEditEnterGuarded
