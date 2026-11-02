/**
 * Drag-to-build on a course slide.
 * The hammer knocks nodes out while editing. Preview drops grade those nodes.
 */
import { computed, ref, shallowRef } from 'vue'

import { readInteract } from '@/composables/training/trainingInteract'
import type { TrainingCourseStep } from '@/types/training'

export const trainingDragKnockActive = ref(false)
/** Teacher is choosing blanks with the hammer. Off after 完成选择. */
export const trainingDragPicking = ref(true)
export const trainingDragDropActive = ref(false)
/** Last drop on a knocked-out node: true matches the stored answer. */
export const trainingDragMarks = ref<Record<string, boolean>>({})
export const trainingDragHint = ref<{
  nodeId: string
  text: string
  editable: boolean
} | null>(null)
/** Correct drops keep the wording on the node after the check fades. */
export const trainingDragFilledIds = ref<string[]>([])

const trainingDragStep = shallowRef<TrainingCourseStep | null>(null)
const trainingDragPlayLocked = ref(false)

const KNOCK_DELAY_MS = 400
export const TRAINING_DRAG_MARK_OK_MS = 10_000
export const TRAINING_DRAG_MARK_BAD_MS = 5_000

const markTimers = new Map<string, number>()

type KnockHandler = (nodeId: string) => void

let onKnock: KnockHandler | null = null
let knockTimer: number | null = null
let knockNodeId: string | null = null

function dragBlanks() {
  const interact = trainingDragStep.value ? readInteract(trainingDragStep.value) : null
  if (!interact || interact.mode !== 'drag') return []
  if (trainingDragPlayLocked.value && interact.sequence_saved !== true) return []
  return interact.blanks
}

export const trainingDragBlankIds = computed(() => dragBlanks().map((row) => row.node_id))

export const trainingDragAnswers = computed(() => {
  const answers: Record<string, string> = {}
  for (const row of dragBlanks()) answers[row.node_id] = row.answer
  return answers
})

export const trainingDragHints = computed(() => {
  const hints: Record<string, string> = {}
  for (const row of dragBlanks()) {
    if (row.hint) hints[row.node_id] = row.hint
  }
  return hints
})

/** Bind the live course step so the diagram and the list share the same blanks. */
export function bindTrainingDragSurface(step: TrainingCourseStep | null, playLocked = false): void {
  trainingDragPlayLocked.value = playLocked
  trainingDragStep.value = step
}

export function registerTrainingDragKnock(handler: KnockHandler): () => void {
  onKnock = handler
  return () => {
    if (onKnock === handler) onKnock = null
  }
}

export function cancelTrainingDragKnock(): void {
  if (knockTimer !== null) window.clearTimeout(knockTimer)
  knockTimer = null
  knockNodeId = null
}

export function setTrainingDragPicking(on: boolean): void {
  trainingDragPicking.value = on
  if (on) return
  cancelTrainingDragKnock()
  trainingDragKnockActive.value = false
}

function clearMarkTimer(nodeId: string): void {
  const timer = markTimers.get(nodeId)
  if (timer !== undefined) window.clearTimeout(timer)
  markTimers.delete(nodeId)
}

function clearAllMarkTimers(): void {
  markTimers.forEach((timer) => window.clearTimeout(timer))
  markTimers.clear()
}

export function clearTrainingDragMarks(): void {
  clearAllMarkTimers()
  trainingDragMarks.value = {}
  trainingDragFilledIds.value = []
}

function scheduleMarkClear(nodeId: string, delayMs: number): void {
  clearMarkTimer(nodeId)
  markTimers.set(
    nodeId,
    window.setTimeout(() => {
      markTimers.delete(nodeId)
      const next = { ...trainingDragMarks.value }
      delete next[nodeId]
      trainingDragMarks.value = next
    }, delayMs)
  )
}

/** True when the hammer owns the click. A double-click cancels the knock. */
export function trainingDragKnockNode(nodeId: string): boolean {
  if (!trainingDragKnockActive.value || !trainingDragPicking.value || !onKnock || !nodeId) {
    return false
  }
  cancelTrainingDragKnock()
  knockNodeId = nodeId
  knockTimer = window.setTimeout(() => {
    knockTimer = null
    const id = knockNodeId
    knockNodeId = null
    if (id && trainingDragKnockActive.value) onKnock?.(id)
  }, KNOCK_DELAY_MS)
  return true
}

export function openTrainingDragHint(nodeId: string, text: string, editable: boolean): void {
  if (!nodeId) return
  trainingDragHint.value = { nodeId, text, editable }
}

export function closeTrainingDragHint(): void {
  trainingDragHint.value = null
}

/** After a graded miss, show the teacher-written hint for that node. */
export function noteTrainingDragWrongDrop(nodeId: string): void {
  if (!trainingDragDropActive.value) return
  if (!trainingDragBlankIds.value.includes(nodeId)) return
  if (trainingDragFilledIds.value.includes(nodeId)) return
  openTrainingDragHint(nodeId, trainingDragHints.value[nodeId] ?? '', false)
}

export function trainingDragDropOnNode(nodeId: string, given: string): boolean {
  if (!trainingDragDropActive.value || !trainingDragBlankIds.value.includes(nodeId)) return false
  if (trainingDragFilledIds.value.includes(nodeId)) return false
  const answer = trainingDragAnswers.value[nodeId]
  if (answer === undefined) return false
  const ok = given.trim() === answer.trim()
  trainingDragMarks.value = { ...trainingDragMarks.value, [nodeId]: ok }
  if (ok) trainingDragFilledIds.value = [...trainingDragFilledIds.value, nodeId]
  scheduleMarkClear(nodeId, ok ? TRAINING_DRAG_MARK_OK_MS : TRAINING_DRAG_MARK_BAD_MS)
  return ok
}

export function clearTrainingDragSurface(): void {
  cancelTrainingDragKnock()
  trainingDragKnockActive.value = false
  trainingDragPicking.value = true
  trainingDragDropActive.value = false
  bindTrainingDragSurface(null)
  closeTrainingDragHint()
  clearTrainingDragMarks()
}
