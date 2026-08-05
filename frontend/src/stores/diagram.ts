/**
 * Diagram Store - Pinia store for the editor diagram session.
 * Session assembly lives in createDiagramSession (also used for Showcase preview).
 */
import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'

import {
  EDITOR_DIAGRAM_VUE_FLOW_ID,
  adaptGlobalEventBusAsViewBus,
} from './diagram/diagramViewBus'
import { createDiagramSession } from './diagram/createDiagramSession'

export { subscribeToDiagramEvents } from './diagram/events'
export type {
  DiagramEvent,
  DiagramEventType,
  LoadFromSpecOptions,
  MindMapCurveExtents,
} from './diagram/types'
export {
  asDiagramSession,
  createDiagramSession,
  type CreateDiagramSessionOptions,
  type DiagramSession,
  type DiagramSessionMode,
  type DiagramSessionRaw,
} from './diagram/createDiagramSession'
export {
  EDITOR_DIAGRAM_VUE_FLOW_ID,
  createDiagramViewBus,
  type DiagramViewBus,
} from './diagram/diagramViewBus'

export const useDiagramStore = defineStore('diagram', () =>
  createDiagramSession({
    mode: 'edit',
    vueFlowId: EDITOR_DIAGRAM_VUE_FLOW_ID,
    viewBus: adaptGlobalEventBusAsViewBus(eventBus),
    emitDiagramEvents: true,
  })
)
