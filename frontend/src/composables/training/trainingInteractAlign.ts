/**
 * Keep guided-reading / drag-to-build records on the same nodes as the live diagram.
 */
import type { TrainingCourseStep } from '@/types/training'
import { assignTrainingStepField } from '@/utils/trainingStepPatch'

import { type BuilderDiagramNode } from './builderDiagramBridge'
import { readInteract, writeInteract } from './trainingInteract'

function sameIds(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((id, index) => id === right[index])
}

function keptReadOrder(order: readonly string[], nodes: readonly BuilderDiagramNode[]): string[] {
  const known = new Set(nodes.map((node) => node.id))
  const next = order.filter((id) => known.has(id))
  for (const node of nodes) {
    if (!next.includes(node.id)) next.push(node.id)
  }
  return next
}

function readSavedCollapsed(previous: readonly string[], next: readonly string[]): boolean {
  return previous.length > 0 && next.length > 0 && next.every((id) => !previous.includes(id))
}

/**
 * Rewrite interact + node-linked overlays so they match the current canvas nodes.
 * Returns true when the course step changed.
 */
export function alignInteractWithDiagram(
  step: TrainingCourseStep,
  nodes: readonly BuilderDiagramNode[]
): boolean {
  const interact = readInteract(step)
  if (!interact || nodes.length === 0) return false
  const known = new Map(nodes.map((node) => [node.id, node]))
  let changed = false

  const nextOrder =
    interact.mode === 'read'
      ? keptReadOrder(interact.read_order, nodes)
      : interact.read_order.filter((id) => known.has(id))
  if (!sameIds(nextOrder, interact.read_order)) changed = true

  const nextBlanks = interact.blanks.flatMap((row) => {
    const node = known.get(row.node_id)
    if (!node) {
      changed = true
      return []
    }
    const answer = node.text.trim() || node.id
    if (answer === row.answer) return [row]
    changed = true
    return [{ ...row, answer }]
  })

  const nextExtras = interact.node_extras.filter((row) => known.has(row.node_id))
  if (nextExtras.length !== interact.node_extras.length) changed = true

  const nextQuizzes = interact.quizzes.filter((row) => !row.node_id || known.has(row.node_id))
  if (nextQuizzes.length !== interact.quizzes.length) changed = true

  let sequenceSaved = interact.sequence_saved
  if (interact.mode === 'drag' && nextBlanks.length === 0) sequenceSaved = false
  if (interact.mode === 'read' && nextOrder.length === 0) sequenceSaved = false
  if (interact.mode === 'read' && readSavedCollapsed(interact.read_order, nextOrder)) {
    sequenceSaved = false
  }
  if (sequenceSaved !== interact.sequence_saved) changed = true

  if (changed) {
    writeInteract(step, {
      ...interact,
      read_order: nextOrder,
      blanks: nextBlanks,
      node_extras: nextExtras,
      quizzes: nextQuizzes,
      sequence_saved: sequenceSaved,
    })
  }

  const overlays = step.overlays
  if (!overlays?.length) return changed
  const nextOverlays = overlays.filter((overlay) => !overlay.node_id || known.has(overlay.node_id))
  if (nextOverlays.length === overlays.length) return changed
  assignTrainingStepField(step, 'overlays', nextOverlays)
  return true
}
