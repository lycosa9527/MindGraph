/**
 * Course-builder interactions stored on a slide: guided reading, drag-to-build, quiz.
 */
import { ref } from 'vue'

import type {
  TrainingCourseStep,
  TrainingInteract,
  TrainingInteractBlank,
  TrainingInteractChoice,
  TrainingInteractExtraKind,
  TrainingInteractMode,
  TrainingInteractNodeExtra,
  TrainingInteractQuiz,
  TrainingStepOverlay,
} from '@/types/training'
import { assignTrainingStepField } from '@/utils/trainingStepPatch'

import { type BuilderDiagramNode, builderDiagramNodes } from './builderDiagramBridge'

const CHOICE_IDS = ['a', 'b', 'c'] as const
const EXTRA_KINDS = [
  'note',
  'mascot',
  'video',
  'image',
] as const satisfies readonly TrainingInteractExtraKind[]

/** Shared with the ribbon stepper and the order list beside the canvas. */
export const interactReadCursor = ref(0)

export function emptyInteract(mode: TrainingInteractMode = 'read'): TrainingInteract {
  return {
    mode,
    read_order: [],
    blanks: [],
    quizzes: [],
    sequence_saved: false,
    node_extras: [],
  }
}

export function readInteract(step: TrainingCourseStep): TrainingInteract | null {
  const raw = step.interact
  if (!raw || (raw.mode !== 'read' && raw.mode !== 'drag' && raw.mode !== 'quiz')) return null
  return {
    mode: raw.mode,
    read_order: Array.isArray(raw.read_order) ? raw.read_order.filter((id) => id) : [],
    blanks: readBlanks(raw.blanks),
    quizzes: Array.isArray(raw.quizzes) ? raw.quizzes : [],
    sequence_saved: raw.sequence_saved === true && (raw.mode === 'read' || raw.mode === 'drag'),
    node_extras: readNodeExtras(raw.node_extras),
  }
}

function readNodeExtras(raw: unknown): TrainingInteractNodeExtra[] {
  if (!Array.isArray(raw)) return []
  const rows: TrainingInteractNodeExtra[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const nodeId = 'node_id' in item && typeof item.node_id === 'string' ? item.node_id : ''
    if (!nodeId) continue
    const kindsRaw = 'kinds' in item && Array.isArray(item.kinds) ? item.kinds : []
    const kinds = EXTRA_KINDS.filter((kind) => kindsRaw.includes(kind))
    if (kinds.length === 0) continue
    const vod =
      'vod_media_id' in item && typeof item.vod_media_id === 'string' ? item.vod_media_id : ''
    const row: TrainingInteractNodeExtra = { node_id: nodeId, kinds: [...kinds] }
    if (vod && kinds.includes('video')) row.vod_media_id = vod
    rows.push(row)
  }
  return rows
}

function readBlanks(raw: unknown): TrainingInteractBlank[] {
  if (!Array.isArray(raw)) return []
  const rows: TrainingInteractBlank[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object' || !('node_id' in item)) continue
    const nodeId = typeof item.node_id === 'string' ? item.node_id : ''
    if (!nodeId) continue
    const answer = 'answer' in item && typeof item.answer === 'string' ? item.answer : ''
    const hint = 'hint' in item && typeof item.hint === 'string' ? item.hint.trim() : ''
    const row: TrainingInteractBlank = { node_id: nodeId, answer }
    if (hint) row.hint = hint
    rows.push(row)
  }
  return rows
}

export function writeInteract(step: TrainingCourseStep, next: TrainingInteract | null): void {
  assignTrainingStepField(step, 'interact', next)
}

export function setInteractMode(step: TrainingCourseStep, mode: TrainingInteractMode | null): void {
  if (!mode) {
    writeInteract(step, null)
    return
  }
  const current = readInteract(step) ?? emptyInteract(mode)
  writeInteract(step, {
    ...current,
    mode,
    sequence_saved: current.mode === mode && current.sequence_saved,
  })
}

export function orderedReadNodes(
  nodes: readonly BuilderDiagramNode[],
  order: readonly string[]
): BuilderDiagramNode[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const used = new Set<string>()
  const rows: BuilderDiagramNode[] = []
  for (const id of order) {
    const node = byId.get(id)
    if (!node || used.has(node.id)) continue
    used.add(node.id)
    rows.push(node)
  }
  for (const node of nodes) {
    if (used.has(node.id)) continue
    rows.push(node)
  }
  return rows
}

export function reorderReadIds(
  ids: readonly string[],
  fromIndex: number,
  toIndex: number
): string[] {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return [...ids]
  if (fromIndex >= ids.length || toIndex >= ids.length) return [...ids]
  const next = [...ids]
  const moved = next.splice(fromIndex, 1)[0]
  if (!moved) return [...ids]
  next.splice(toIndex, 0, moved)
  return next
}

export function setReadOrder(step: TrainingCourseStep, nodeIds: readonly string[]): void {
  const current = readInteract(step) ?? emptyInteract('read')
  writeInteract(step, {
    ...current,
    mode: 'read',
    read_order: nodeIds.filter((id) => id),
  })
}

/** Persist the teacher’s knock-list order. Keeps hints and the play-ready flag. */
export function setDragBlankOrder(step: TrainingCourseStep, nodeIds: readonly string[]): void {
  const current = readInteract(step) ?? emptyInteract('drag')
  const byId = new Map(current.blanks.map((row) => [row.node_id, row]))
  const blanks: TrainingInteractBlank[] = []
  const used = new Set<string>()
  for (const id of nodeIds) {
    const row = byId.get(id)
    if (!row || used.has(id)) continue
    used.add(id)
    blanks.push(row)
  }
  for (const row of current.blanks) {
    if (used.has(row.node_id)) continue
    blanks.push(row)
  }
  writeInteract(step, { ...current, mode: 'drag', blanks })
}

function overlayLink(overlay: TrainingStepOverlay): TrainingInteractExtraKind | null {
  if (overlay.kind === 'text' && overlay.node_id) return 'note'
  if (overlay.kind !== 'role' || !overlay.node_id || !overlay.asset_id) return null
  return overlay.link === 'image' ? 'image' : 'mascot'
}

export function nodeHasLink(
  step: TrainingCourseStep,
  nodeId: string,
  kind: TrainingInteractExtraKind
): boolean {
  if (kind === 'video') return Boolean(nodeVodId(step, nodeId))
  return (step.overlays || []).some(
    (overlay) => overlay.node_id === nodeId && overlayLink(overlay) === kind
  )
}

export function setNodeVideo(step: TrainingCourseStep, nodeId: string, vodId: string | null): void {
  const current = readInteract(step) ?? emptyInteract('read')
  const node_extras = current.node_extras.filter((row) => row.node_id !== nodeId)
  if (vodId) node_extras.push({ node_id: nodeId, kinds: ['video'], vod_media_id: vodId })
  writeInteract(step, { ...current, mode: 'read', node_extras })
}

/** Saved guided-reading order. Empty until the teacher commits the list. */
export function savedReadOrder(step: TrainingCourseStep | null | undefined): string[] {
  const interact = step?.interact
  if (!interact || interact.mode !== 'read' || interact.sequence_saved !== true) return []
  return (interact.read_order || []).filter((id) => id)
}

export function readPlayIndex(step: TrainingCourseStep, count: number): number {
  if (count <= 0) return 0
  const raw = step.interact?.play_index
  const cursor = typeof raw === 'number' && Number.isFinite(raw) ? raw : interactReadCursor.value
  return Math.min(count - 1, Math.max(0, Math.round(cursor)))
}

export function nodeVodId(step: TrainingCourseStep, nodeId: string | null): string | null {
  if (!nodeId) return null
  const row = readInteract(step)?.node_extras.find((item) => item.node_id === nodeId)
  return row?.vod_media_id || null
}

/**
 * The order the dock, the ribbon, and playback share.
 * Saved ids come first; nodes added after the save follow them.
 */
export function playOrderIds(step: TrainingCourseStep): string[] {
  const interact = readInteract(step)
  if (!interact || interact.mode !== 'read') return []
  const saved = interact.read_order.filter((id) => id)
  const live = builderDiagramNodes.value
  if (interact.sequence_saved && saved.length > 0) {
    if (live.length === 0) return saved
    const known = new Set(live.map((node) => node.id))
    const listed = saved.filter((id) => known.has(id))
    const extra = live.filter((node) => !saved.includes(node.id)).map((node) => node.id)
    return listed.length > 0 ? [...listed, ...extra] : extra
  }
  const listed = orderedReadNodes(live, saved)
  return listed.map((node) => node.id)
}

/** Node the guided-reading walk is showing. Null hides node-linked marks. */
export function readFocusNodeId(step: TrainingCourseStep): string | null {
  const ids = playOrderIds(step)
  if (ids.length === 0) return null
  return ids[readPlayIndex(step, ids.length)] ?? null
}

export function overlaysForReadNode(
  overlays: readonly TrainingStepOverlay[],
  nodeId: string | null
): TrainingStepOverlay[] {
  return overlays.filter((overlay) => !overlay.node_id || overlay.node_id === nodeId)
}

export function saveReadSequence(step: TrainingCourseStep, nodeIds: readonly string[]): void {
  const current = readInteract(step) ?? emptyInteract('read')
  writeInteract(step, {
    ...current,
    mode: 'read',
    read_order: nodeIds.filter((id) => id),
    sequence_saved: true,
  })
}

export function toggleInteractBlank(step: TrainingCourseStep, node: BuilderDiagramNode): void {
  const current = readInteract(step) ?? emptyInteract('drag')
  const exists = current.blanks.some((row) => row.node_id === node.id)
  const blanks: TrainingInteractBlank[] = exists
    ? current.blanks.filter((row) => row.node_id !== node.id)
    : [...current.blanks, { node_id: node.id, answer: node.text }]
  writeInteract(step, { ...current, mode: 'drag', blanks, sequence_saved: false })
}

export function setInteractBlankHint(step: TrainingCourseStep, nodeId: string, hint: string): void {
  const current = readInteract(step) ?? emptyInteract('drag')
  const trimmed = hint.trim()
  const blanks = current.blanks.map((row) => {
    if (row.node_id !== nodeId) return row
    if (!trimmed) {
      const next = { ...row }
      delete next.hint
      return next
    }
    return { ...row, hint: trimmed }
  })
  writeInteract(step, { ...current, mode: 'drag', blanks })
}

/** Commits the knocked-out nodes so preview and the course can play them. */
export function saveDragBlanks(step: TrainingCourseStep): void {
  const current = readInteract(step) ?? emptyInteract('drag')
  if (current.mode !== 'drag' || current.blanks.length === 0) return
  writeInteract(step, { ...current, mode: 'drag', sequence_saved: true })
}

function blankChoice(id: string): TrainingInteractChoice {
  return { id, label: '', correct: false }
}

export function ensureQuiz(step: TrainingCourseStep, nodeId: string): TrainingInteractQuiz {
  const current = readInteract(step) ?? emptyInteract('quiz')
  const found = current.quizzes.find((quiz) => quiz.node_id === nodeId)
  if (found) return found
  return {
    node_id: nodeId,
    prompt: '',
    choices: CHOICE_IDS.map((id) => blankChoice(id)),
  }
}

export function saveQuiz(step: TrainingCourseStep, quiz: TrainingInteractQuiz): void {
  const current = readInteract(step) ?? emptyInteract('quiz')
  const quizzes = current.quizzes.filter((row) => row.node_id !== quiz.node_id)
  writeInteract(step, { ...current, mode: 'quiz', quizzes: [...quizzes, quiz] })
}

export function shuffledBlanks(blanks: readonly TrainingInteractBlank[]): TrainingInteractBlank[] {
  return [...blanks].sort((left, right) => mix(left.node_id) - mix(right.node_id))
}

function mix(text: string): number {
  let hash = 0
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 33 + text.charCodeAt(index)) % 997
  }
  return hash
}
