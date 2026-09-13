/**
 * Format painter session — Word-like click-to-apply, shared across toolbars.
 * Listeners live on the event bus (not a component watch) so ribbon remounts
 * and floating-toolbar unmounts cannot drop the apply path.
 */
import { ref } from 'vue'

import {
  FORMAT_BRUSH_DOUBLE_CLICK_MS,
  collectFormatBrushStyle,
  formatBrushTargetsFromSelection,
  resolveFormatPainterClick,
} from '@/composables/canvasToolbar/formatBrushStyle'
import { eventBus } from '@/composables/core/useEventBus'
import { useNotifications } from '@/composables/core/useNotifications'
import { resolveMindMapNodeShape } from '@/config/mindMapDiagramStyles'
import { getMindMapThemeForDiagram, mindMapStyleFromTheme } from '@/config/mindMapThemes'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores/diagram'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
import type { DiagramNode, NodeStyle } from '@/types'
import { safeI18nTranslate } from '@/utils/safeI18nTranslate'

export const formatBrushActive = ref(false)
export const formatBrushLocked = ref(false)

const formatBrushStyle = ref<NodeStyle | null>(null)
const formatBrushSourceIds = ref<string[]>([])

let lastFormatBrushClickAt = 0
let suppressPaneCancel = false
let formatBrushActivateToastTimer: ReturnType<typeof setTimeout> | null = null
let formatBrushListenersBound = false

function toast() {
  return useNotifications()
}

function t(key: string, named?: Record<string, unknown>): string {
  return safeI18nTranslate(
    (lookup, values) => (values ? i18n.global.t(lookup, values) : i18n.global.t(lookup)),
    key,
    named
  )
}

function storeBlocksPaint(): boolean {
  const store = useDiagramStore()
  return isDiagramPresentationReadOnly({ isReadonly: store.isReadonly })
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return target.isContentEditable
}

function syncFormatBrushCursor(active: boolean): void {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('mg-format-brush-active', active)
}

export function resetFormatBrushState(): void {
  formatBrushActive.value = false
  formatBrushLocked.value = false
  formatBrushStyle.value = null
  formatBrushSourceIds.value = []
  lastFormatBrushClickAt = 0
  suppressPaneCancel = false
  if (formatBrushActivateToastTimer !== null) {
    clearTimeout(formatBrushActivateToastTimer)
    formatBrushActivateToastTimer = null
  }
  syncFormatBrushCursor(false)
}

function snapshotFormatBrushStyle(nodeId: string): NodeStyle | null {
  const store = useDiagramStore()
  const sourceNode = store.data?.nodes?.find((node) => node.id === nodeId)
  if (!sourceNode) return null
  const persisted = store.getNodeStyle(nodeId)
  const isMindMap = store.type === 'mindmap' || store.type === 'mind_map'
  const themeFallback = isMindMap
    ? mindMapStyleFromTheme(
        sourceNode,
        getMindMapThemeForDiagram(store.data),
        store.data?._mindmap_diagram_style,
        store.data?.connections
      )
    : undefined
  const copied = collectFormatBrushStyle(sourceNode.style, persisted, themeFallback)
  if (!copied.nodeShape && isMindMap) {
    copied.nodeShape = resolveMindMapNodeShape(
      {
        id: sourceNode.id,
        type: sourceNode.type,
        style: { ...themeFallback, ...persisted, ...sourceNode.style },
      },
      store.data?._mindmap_diagram_style
    )
  }
  return copied
}

function applyCopiedFormatBrush(ids: string[]): void {
  const style = formatBrushStyle.value
  if (!style || ids.length === 0) return
  if (storeBlocksPaint()) {
    resetFormatBrushState()
    return
  }
  const store = useDiagramStore()
  const nodes = ids
    .map((nodeId) => store.data?.nodes?.find((item) => item.id === nodeId))
    .filter((node): node is DiagramNode => Boolean(node))
  if (nodes.length === 0) return
  store.pushHistory(t('canvas.toolbar.formatPainter'))
  const paintedIds: string[] = []
  nodes.forEach((node) => {
    if (store.updateNode(node.id, { style: { ...(node.style || {}), ...style } })) {
      paintedIds.push(node.id)
    }
  })
  if (paintedIds.length === 0) return
  suppressPaneCancel = true
  queueMicrotask(() => {
    suppressPaneCancel = false
  })
  if (formatBrushLocked.value) {
    formatBrushSourceIds.value = [...formatBrushSourceIds.value, ...paintedIds]
    return
  }
  resetFormatBrushState()
  toast().success(t('canvas.toolbar.formatBrushApplied', { count: paintedIds.length }))
}

function cancelCopiedFormatBrush(options?: { silent?: boolean }): void {
  if (!formatBrushActive.value) return
  resetFormatBrushState()
  if (!options?.silent) toast().info(t('canvas.toolbar.formatBrushCancelled'))
}

function onFormatBrushSelectionChanged(payload: { selectedNodes: string[] }): void {
  if (!formatBrushActive.value || !formatBrushStyle.value) return
  const targets = formatBrushTargetsFromSelection(
    payload.selectedNodes ?? [],
    formatBrushSourceIds.value
  )
  if (!targets.length) return
  applyCopiedFormatBrush(targets)
}

function onFormatBrushNodeClicked(payload: { nodeId: string }): void {
  applyFormatBrushToNode(payload.nodeId)
}

function onFormatBrushPaneClick(): void {
  if (!formatBrushActive.value || suppressPaneCancel) return
  cancelCopiedFormatBrush()
}

function onFormatBrushEscape(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !formatBrushActive.value) return
  if (event.defaultPrevented || event.isComposing || isTypingTarget(event.target)) return
  cancelCopiedFormatBrush()
}

function onFormatBrushSessionEnded(): void {
  resetFormatBrushState()
}

export function ensureFormatBrushListeners(): void {
  if (formatBrushListenersBound) return
  formatBrushListenersBound = true
  eventBus.on('state:selection_changed', onFormatBrushSelectionChanged)
  eventBus.on('canvas:node_clicked', onFormatBrushNodeClicked)
  eventBus.on('canvas:pane_clicked', onFormatBrushPaneClick)
  eventBus.on('diagram:loaded', onFormatBrushSessionEnded)
  eventBus.on('diagram:type_changed', onFormatBrushSessionEnded)
  eventBus.on('diagram:loaded_from_library', onFormatBrushSessionEnded)
  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', onFormatBrushEscape)
  }
}

export function applyFormatBrushToNode(nodeId: string): boolean {
  ensureFormatBrushListeners()
  if (!formatBrushActive.value || !formatBrushStyle.value || !nodeId) return false
  const targets = formatBrushTargetsFromSelection([nodeId], formatBrushSourceIds.value)
  if (!targets.length) return false
  applyCopiedFormatBrush(targets)
  return true
}

function pickupFormatBrush(lock: boolean): boolean {
  if (storeBlocksPaint()) return false
  const store = useDiagramStore()
  const sourceIds = store.selectedNodes
  const sourceId = sourceIds[0]
  if (!sourceId) {
    toast().warning(t('canvas.toolbar.formatBrushSelectSource'))
    return false
  }
  const copiedStyle = snapshotFormatBrushStyle(sourceId)
  if (!copiedStyle || Object.keys(copiedStyle).length === 0) return false
  formatBrushStyle.value = copiedStyle
  formatBrushSourceIds.value = [...sourceIds]
  formatBrushActive.value = true
  formatBrushLocked.value = lock
  syncFormatBrushCursor(true)
  return true
}

function announceFormatBrushMode(lock: boolean): void {
  if (formatBrushActivateToastTimer !== null) {
    clearTimeout(formatBrushActivateToastTimer)
    formatBrushActivateToastTimer = null
  }
  if (lock) {
    toast().success(t('canvas.toolbar.formatBrushActivated'))
    return
  }
  formatBrushActivateToastTimer = setTimeout(() => {
    formatBrushActivateToastTimer = null
    if (formatBrushActive.value && !formatBrushLocked.value) {
      toast().success(t('canvas.toolbar.formatBrushActivated'))
    }
  }, FORMAT_BRUSH_DOUBLE_CLICK_MS)
}

export function handleFormatBrush(options?: { lock?: boolean }): void {
  ensureFormatBrushListeners()
  const now = Date.now()
  const action = resolveFormatPainterClick({
    active: formatBrushActive.value,
    locked: formatBrushLocked.value,
    lockRequested: Boolean(options?.lock),
    elapsedMs: now - lastFormatBrushClickAt,
  })
  lastFormatBrushClickAt = now

  if (action === 'noop') return
  if (action === 'cancel') {
    cancelCopiedFormatBrush()
    return
  }

  if (action === 'activate') {
    if (!pickupFormatBrush(false)) return
    announceFormatBrushMode(false)
    return
  }

  if (!formatBrushActive.value) {
    if (!pickupFormatBrush(true)) return
  } else {
    formatBrushLocked.value = true
  }
  announceFormatBrushMode(true)
}

export function useCanvasFormatBrush() {
  ensureFormatBrushListeners()
  return {
    formatBrushActive,
    formatBrushLocked,
    handleFormatBrush,
    applyFormatBrushToNode,
  }
}
