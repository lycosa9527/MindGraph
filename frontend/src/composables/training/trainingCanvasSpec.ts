/**
 * Course canvas spec lives on the slide. The builder session is only the editor.
 */
import {
  builderDiagramSession,
  clearBuilderDiagramBinding,
  isBoundToStep,
  matchBoundBuilderStep,
} from '@/composables/training/builderDiagramBridge'
import type { DiagramSession } from '@/stores/diagram'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourseStep } from '@/types/training'
import { cloneShowcaseDiagramSpec } from '@/utils/showcaseDiagramThumbnail'
import { assignTrainingStepField } from '@/utils/trainingStepPatch'

export function isTrainingDiagramSpec(raw: unknown): raw is Record<string, unknown> {
  return Boolean(raw) && typeof raw === 'object' && !Array.isArray(raw)
}

export function readStepDiagramSpec(
  step: TrainingCourseStep | null | undefined
): Record<string, unknown> | null {
  return isTrainingDiagramSpec(step?.diagram_spec) ? step.diagram_spec : null
}

function specNodeIds(spec: Record<string, unknown>): string[] {
  if (!Array.isArray(spec.nodes)) return []
  return spec.nodes
    .map((node) =>
      node && typeof node === 'object' && typeof (node as { id?: unknown }).id === 'string'
        ? (node as { id: string }).id
        : ''
    )
    .filter(Boolean)
}

function specConnectionCount(spec: Record<string, unknown>): number {
  return Array.isArray(spec.connections) ? spec.connections.length : 0
}

function hasMindMapBranchTree(spec: Record<string, unknown>): boolean {
  return (
    (Array.isArray(spec.children) && spec.children.length > 0) ||
    (Array.isArray(spec.leftBranches) && spec.leftBranches.length > 0) ||
    (Array.isArray(spec.rightBranches) && spec.rightBranches.length > 0)
  )
}

/** A topic-only snapshot must not replace a saved tree (remount / half-loaded session). */
export function shouldReplaceDiagramSpec(
  previous: Record<string, unknown> | null | undefined,
  next: Record<string, unknown>
): boolean {
  if (!previous) return true
  const previousHasTree =
    specNodeIds(previous).length > 1 ||
    specConnectionCount(previous) > 0 ||
    hasMindMapBranchTree(previous)
  const nextIsTopicOnly = specNodeIds(next).length <= 1 && specConnectionCount(next) === 0
  if (previousHasTree && nextIsTopicOnly && !hasMindMapBranchTree(next)) return false
  return true
}

/** Prefer the original branch tree when a later write left only the center node. */
export function preferMindMapTreeIfRicher(spec: Record<string, unknown>): Record<string, unknown> {
  if (!hasMindMapBranchTree(spec)) return spec
  if (specNodeIds(spec).length > 1 && specConnectionCount(spec) > 0) return spec
  const next = { ...spec }
  delete next.nodes
  delete next.connections
  return next
}

export function writeStepDiagramSpec(step: TrainingCourseStep, session: DiagramSession): boolean {
  const spec = session.getSpecForSave()
  if (!spec || !isTrainingDiagramSpec(spec)) return false
  const snapshot = cloneShowcaseDiagramSpec(spec)
  const previous = step.diagram_spec
  if (previous && JSON.stringify(previous) === JSON.stringify(snapshot)) return false
  if (!shouldReplaceDiagramSpec(previous, snapshot)) return false
  assignTrainingStepField(step, 'diagram_spec', snapshot)
  return true
}

export function isCanvasCourseStep(
  step: TrainingCourseStep | null | undefined
): step is TrainingCourseStep {
  if (!step) return false
  return step.page_key === 'canvas' || step.type === 'canvas'
}

/** Copy the live session onto the slide it is bound to, never the merely selected one. */
export function flushPublishedBuilderSpec(): void {
  const session = builderDiagramSession.value
  const step = matchBoundBuilderStep(useTrainingBuilderStore().steps)
  if (!session || !isCanvasCourseStep(step)) return
  writeStepDiagramSpec(step, session)
}

export function releaseBuilderDiagramBinding(
  session: DiagramSession | null,
  step?: TrainingCourseStep | null
): void {
  const live = builderDiagramSession.value
  if (live && session && live !== session) return
  if (live && !session && step && !isBoundToStep(step)) return
  if (!live && session) return
  clearBuilderDiagramBinding()
}
