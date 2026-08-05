/**
 * Per-session view event bus for diagram canvas fit/zoom.
 * Editor sessions may use the global app eventBus; Showcase preview uses a private bus.
 */
import mitt, { type Emitter, type Handler } from 'mitt'

import type { EventTypes } from '@/composables/core/useEventBus'

/** View / canvas-local events that must not cross diagram sessions. */
export type DiagramViewEventKey =
  | 'view:fit_to_window_requested'
  | 'view:fit_to_canvas_requested'
  | 'view:fit_to_nodes_requested'
  | 'view:ensure_node_visible_requested'
  | 'view:fit_diagram_requested'
  | 'view:fit_for_export_requested'
  | 'view:fit_completed'
  | 'view:zoom_in_requested'
  | 'view:zoom_out_requested'
  | 'view:zoom_set_requested'
  | 'view:zoom_changed'
  | 'view:viewport_snapshot_save'
  | 'view:viewport_snapshot_restore'
  | 'node:edit_requested'
  | 'diagram:branch_moved'
  | 'diagram:double_bubble_relayout_requested'
  | 'diagram:loaded'
  | 'diagram:loaded_from_library'
  | 'multi_flow_map:topic_width_changed'
  | 'multi_flow_map:node_width_changed'

type ViewEventMap = {
  [K in DiagramViewEventKey]: EventTypes[K]
}

export interface DiagramViewBus {
  on<K extends DiagramViewEventKey>(event: K, handler: (data: ViewEventMap[K]) => void): () => void
  once<K extends DiagramViewEventKey>(event: K, handler: (data: ViewEventMap[K]) => void): () => void
  off<K extends DiagramViewEventKey>(event: K, handler?: (data: ViewEventMap[K]) => void): void
  emit<K extends DiagramViewEventKey>(event: K, data: ViewEventMap[K]): void
  clear: () => void
}

function wrapMitt(emitter: Emitter<ViewEventMap>): DiagramViewBus {
  return {
    on<K extends DiagramViewEventKey>(event: K, handler: (data: ViewEventMap[K]) => void) {
      const h = handler as Handler<ViewEventMap[K]>
      emitter.on(event, h)
      return () => {
        emitter.off(event, h)
      }
    },
    once<K extends DiagramViewEventKey>(event: K, handler: (data: ViewEventMap[K]) => void) {
      const onceHandler: Handler<ViewEventMap[K]> = (data) => {
        emitter.off(event, onceHandler)
        handler(data)
      }
      emitter.on(event, onceHandler)
      return () => {
        emitter.off(event, onceHandler)
      }
    },
    off<K extends DiagramViewEventKey>(event: K, handler?: (data: ViewEventMap[K]) => void) {
      if (handler) {
        emitter.off(event, handler as Handler<ViewEventMap[K]>)
        return
      }
      emitter.off(event)
    },
    emit<K extends DiagramViewEventKey>(event: K, data: ViewEventMap[K]) {
      emitter.emit(event, data)
    },
    clear() {
      emitter.all.clear()
    },
  }
}

/** Private mitt bus for Showcase / secondary diagram sessions. */
export function createDiagramViewBus(): DiagramViewBus {
  return wrapMitt(mitt<ViewEventMap>())
}

/**
 * Adapt the global app eventBus to DiagramViewBus for the editor session.
 * View events stay on the process bus so existing CanvasPage listeners keep working.
 */
/** Minimal surface of the app eventBus used for editor view-bus forwarding. */
type GlobalEventBusViewAdapter = {
  // EnhancedEventBus methods are generic; keep this adapter structurally loose.
  on: (event: DiagramViewEventKey, handler: (data: ViewEventMap[DiagramViewEventKey]) => void) => () => void
  once: (
    event: DiagramViewEventKey,
    handler: (data: ViewEventMap[DiagramViewEventKey]) => void
  ) => () => void
  off: (
    event: DiagramViewEventKey,
    handler?: (data: ViewEventMap[DiagramViewEventKey]) => void
  ) => void
  emit: (event: DiagramViewEventKey, data: ViewEventMap[DiagramViewEventKey]) => void
}

export function adaptGlobalEventBusAsViewBus(globalBus: unknown): DiagramViewBus {
  const bus = globalBus as GlobalEventBusViewAdapter
  return {
    on(event, handler) {
      return bus.on(event, handler as (data: ViewEventMap[DiagramViewEventKey]) => void)
    },
    once(event, handler) {
      return bus.once(event, handler as (data: ViewEventMap[DiagramViewEventKey]) => void)
    },
    off(event, handler) {
      bus.off(event, handler as ((data: ViewEventMap[DiagramViewEventKey]) => void) | undefined)
    },
    emit(event, data) {
      bus.emit(event, data)
    },
    clear() {
      // Never clear the global app bus.
    },
  }
}

export const EDITOR_DIAGRAM_VUE_FLOW_ID = 'editor'
