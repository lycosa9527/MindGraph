/**
 * The course-builder canvas owns its diagram session. The ribbon reads nodes from here.
 */
import { shallowRef } from 'vue'

import type { DiagramSession } from '@/stores/diagram'

export interface BuilderDiagramNode {
  id: string
  text: string
}

export type BuilderBoundStep = { id?: string; position: number }

export const builderDiagramNodes = shallowRef<BuilderDiagramNode[]>([])
export const builderDiagramSession = shallowRef<DiagramSession | null>(null)
const builderDiagramStepId = shallowRef('')
const builderDiagramStepPos = shallowRef<number | null>(null)

export function trainingStepKey(step: BuilderBoundStep | null | undefined): string {
  if (!step) return ''
  return step.id || `pos-${step.position}`
}

function dropSessionFrames(session: DiagramSession | null): void {
  if (!session) return
  pendingFrames.delete(session)
  clearFrameTimers(session)
}

export function bindBuilderDiagramSession(
  session: DiagramSession | null,
  step: BuilderBoundStep | null | undefined
): void {
  const previous = builderDiagramSession.value
  if (previous && previous !== session) dropSessionFrames(previous)
  builderDiagramSession.value = session
  builderDiagramStepId.value = session && step?.id ? step.id : ''
  builderDiagramStepPos.value = session && step ? step.position : null
  if (!session) builderDiagramNodes.value = []
}

export function clearBuilderDiagramBinding(): void {
  dropSessionFrames(builderDiagramSession.value)
  bindBuilderDiagramSession(null, null)
}

export function isBoundToStep(step: BuilderBoundStep | null | undefined): boolean {
  if (!step || !builderDiagramSession.value) return false
  const boundId = builderDiagramStepId.value
  if (boundId && step.id) return boundId === step.id
  return builderDiagramStepPos.value === step.position
}

export function matchBoundBuilderStep<T extends BuilderBoundStep>(
  steps: readonly T[]
): T | null {
  const boundId = builderDiagramStepId.value
  const boundPos = builderDiagramStepPos.value
  if (boundId) {
    const byId = steps.find((step) => step.id === boundId)
    if (byId) return byId
  }
  if (boundPos == null) return null
  return steps.find((step) => step.position === boundPos) ?? null
}

export function syncBoundBuilderStep(steps: readonly BuilderBoundStep[]): void {
  const boundId = builderDiagramStepId.value
  if (!boundId) return
  const step = steps.find((row) => row.id === boundId)
  builderDiagramStepPos.value = step ? step.position : null
  if (!step) clearBuilderDiagramBinding()
}

export function noteBuilderStepsInserted(at: number, count: number): void {
  if (builderDiagramStepId.value || count < 1) return
  const pos = builderDiagramStepPos.value
  if (pos == null || at > pos) return
  builderDiagramStepPos.value = pos + count
}

export function noteBuilderStepRemoved(index: number): void {
  if (builderDiagramStepId.value) return
  const pos = builderDiagramStepPos.value
  if (pos == null || index > pos) return
  if (index === pos) {
    clearBuilderDiagramBinding()
    return
  }
  builderDiagramStepPos.value = pos - 1
}

export function sameBoundStep(
  left: BuilderBoundStep | null | undefined,
  right: BuilderBoundStep | null | undefined
): boolean {
  if (!left || !right) return false
  if (left.id && right.id) return left.id === right.id
  return left.position === right.position
}

const CAROUSEL_MAX_ZOOM = 2.2
const CAROUSEL_DURATION_MS = 1000
const frameTargets = new Set<DiagramSession>()
const frameTimers = new Map<DiagramSession, number[]>()

interface FrameRequest {
  nodeId: string
  occludeRightPx: number
}

const pendingFrames = new Map<DiagramSession, FrameRequest>()
let frameFlushQueued = false

function readInteractDockWidth(): number {
  const dock = document.querySelector('.interact-dock')
  if (!(dock instanceof HTMLElement)) return 0
  return Math.round(dock.getBoundingClientRect().width)
}

/** Preview canvases listen here so an order-list click frames the visible diagram. */
export function registerBuilderFrameTarget(session: DiagramSession): () => void {
  frameTargets.add(session)
  return () => {
    frameTargets.delete(session)
    const pending = frameTimers.get(session) ?? []
    pending.forEach((timer) => window.clearTimeout(timer))
    frameTimers.delete(session)
  }
}

function sessionNodeCount(session: DiagramSession): number {
  const nodes = session.data?.nodes
  return Array.isArray(nodes) ? nodes.length : 0
}

function clearFrameTimers(session: DiagramSession): void {
  const pending = frameTimers.get(session) ?? []
  pending.forEach((timer) => window.clearTimeout(timer))
  frameTimers.delete(session)
}

function emitFrame(session: DiagramSession, request: FrameRequest): void {
  session.selectNodes(request.nodeId)
  session.viewBus.emit('view:fit_to_nodes_requested', {
    nodeIds: [request.nodeId],
    animate: true,
    duration: CAROUSEL_DURATION_MS,
    padding: 0.45,
    maxZoom: CAROUSEL_MAX_ZOOM,
    occludeRightPx: request.occludeRightPx,
    userInitiated: true,
  })
}

function retryFrame(session: DiagramSession, request: FrameRequest): void {
  clearFrameTimers(session)
  const attempt = (): void => {
    if (sessionNodeCount(session) === 0) return
    clearFrameTimers(session)
    emitFrame(session, request)
  }
  frameTimers.set(session, [window.setTimeout(attempt, 120), window.setTimeout(attempt, 480)])
}

function flushFrames(): void {
  frameFlushQueued = false
  const batch = [...pendingFrames.entries()]
  pendingFrames.clear()
  for (const [session, request] of batch) {
    if (sessionNodeCount(session) === 0) {
      retryFrame(session, request)
      continue
    }
    clearFrameTimers(session)
    emitFrame(session, request)
  }
}

export function frameDiagramSession(
  session: DiagramSession,
  nodeId: string,
  occludeRightPx: number
): void {
  pendingFrames.set(session, { nodeId, occludeRightPx })
  if (frameFlushQueued) return
  frameFlushQueued = true
  requestAnimationFrame(() => {
    requestAnimationFrame(flushFrames)
  })
}

export function focusBuilderDiagramNode(
  nodeId: string,
  step?: BuilderBoundStep | null
): void {
  if (!nodeId) return
  const dock = readInteractDockWidth()
  const authoring = builderDiagramSession.value
  if (authoring && (!step || isBoundToStep(step))) {
    frameDiagramSession(authoring, nodeId, dock)
  }
  frameTargets.forEach((session) => {
    if (session === authoring) return
    frameDiagramSession(session, nodeId, 0)
  })
}
