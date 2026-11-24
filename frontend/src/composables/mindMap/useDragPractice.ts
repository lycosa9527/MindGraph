/**
 * Classroom drag-fill practice — independent of 挖空支架图 / learning-sheet mode.
 * Blanks live in session state; the diagram nodes are not mutated.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { notify } from '@/composables/core/notifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { dragPracticeSlotGroup } from '@/composables/mindMap/dragPracticeMatch'
import type { DiagramSession } from '@/stores/diagram'
import { useLearningAssignmentCanvasStore } from '@/stores/learningAssignmentCanvas'
import { pickLearningSheetRandomNodeIds } from '@/stores/specLoader/utils'
import { claimThinkingCoinEvent } from '@/utils/claimThinkingCoinEvent'

export type DragPracticeChip = {
  id: string
  nodeId: string
  text: string
}

export const dragPracticeActive = ref(false)
export const dragPracticeSetupOpen = ref(false)
/** Teacher is clicking nodes to choose blanks before play. */
export const dragPracticePicking = ref(false)
export const dragPracticeBlankIds = ref<string[]>([])
export const dragPracticeAnswers = ref<Record<string, string>>({})
export const dragPracticeChips = ref<DragPracticeChip[]>([])
export const dragPracticeFilledIds = ref<string[]>([])
export const dragPracticeUsedChipIds = ref<string[]>([])
export const dragPracticeMarks = ref<Record<string, boolean>>({})
export const dragPracticeDraggingId = ref<string | null>(null)

const MARK_OK_MS = 2500
const MARK_BAD_MS = 1600
const PICK_CLICK_DELAY_MS = 400
const markTimers = new Map<string, number>()

const PROTECTED_NODE_IDS = new Set([
  'topic',
  'event',
  'flow-topic',
  'left-topic',
  'right-topic',
  'dimension-label',
  'outer-boundary',
])

let pickTimer: ReturnType<typeof setTimeout> | null = null
let pickNodeId: string | null = null

function clearMarkTimer(nodeId: string): void {
  const timer = markTimers.get(nodeId)
  if (timer !== undefined) window.clearTimeout(timer)
  markTimers.delete(nodeId)
}

function clearAllMarkTimers(): void {
  markTimers.forEach((timer) => window.clearTimeout(timer))
  markTimers.clear()
}

function scheduleMarkClear(nodeId: string, delayMs: number): void {
  clearMarkTimer(nodeId)
  markTimers.set(
    nodeId,
    window.setTimeout(() => {
      markTimers.delete(nodeId)
      const next = { ...dragPracticeMarks.value }
      delete next[nodeId]
      dragPracticeMarks.value = next
    }, delayMs)
  )
}

function shuffle<T>(items: T[]): T[] {
  const next = [...items]
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[next[i], next[j]] = [next[j], next[i]]
  }
  return next
}

function isProtectedNodeId(nodeId: string, diagramStore: DiagramSession): boolean {
  if (PROTECTED_NODE_IDS.has(nodeId)) return true
  const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
  if (!node) return true
  return node.type === 'topic' || node.type === 'center' || node.type === 'boundary'
}

function nodeAnswerText(node: { id: string; text?: string; data?: unknown }): string {
  const data = node.data as { hiddenAnswer?: string } | undefined
  const hidden = data?.hiddenAnswer?.trim()
  if (hidden) return hidden
  return String(node.text ?? '').trim()
}

function ensureAuthoringAllowed(): boolean {
  return useLearningAssignmentCanvasStore().showLearningSheet
}

function buildChipsFromBlanks(): DragPracticeChip[] {
  return shuffle(
    dragPracticeBlankIds.value
      .map((nodeId) => {
        const text = dragPracticeAnswers.value[nodeId]?.trim()
        if (!text) return null
        return { id: `chip-${nodeId}`, nodeId, text } satisfies DragPracticeChip
      })
      .filter((row): row is DragPracticeChip => row !== null)
  )
}

function snapshotAnswersForIds(nodeIds: string[]): Record<string, string> {
  const diagramStore = useDiagramSession()
  const answers: Record<string, string> = {}
  for (const nodeId of nodeIds) {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    if (!node) continue
    const text = nodeAnswerText(node)
    if (!text) continue
    answers[nodeId] = text
  }
  return answers
}

function enterPlaySession(): boolean {
  const answers = snapshotAnswersForIds(dragPracticeBlankIds.value)
  const blankIds = Object.keys(answers)
  if (blankIds.length === 0) {
    notify.warningKey('canvas.dragPractice.needBlanks')
    return false
  }
  clearAllMarkTimers()
  dragPracticeBlankIds.value = blankIds
  dragPracticeAnswers.value = answers
  dragPracticeChips.value = buildChipsFromBlanks()
  dragPracticeFilledIds.value = []
  dragPracticeUsedChipIds.value = []
  dragPracticeMarks.value = {}
  dragPracticeDraggingId.value = null
  dragPracticePicking.value = false
  dragPracticeActive.value = true
  dragPracticeSetupOpen.value = false
  void claimThinkingCoinEvent('learning_sheet_enable')
  return true
}

export function isDragPracticeActive(): boolean {
  return dragPracticeActive.value
}

export function isDragPracticeDropActive(): boolean {
  return dragPracticeActive.value
}

export function isDragPracticePicking(): boolean {
  return dragPracticePicking.value
}

/** True while the canvas|options split layout should be active. */
export function isDragPracticeSplitOpen(): boolean {
  return dragPracticeActive.value || dragPracticePicking.value
}

export const dragPracticeRemainingCount = computed(
  () =>
    dragPracticeChips.value.filter((chip) => !dragPracticeFilledIds.value.includes(chip.nodeId))
      .length
)

export const dragPracticeTotalCount = computed(() => dragPracticeChips.value.length)

export const dragPracticeCorrectCount = computed(() => dragPracticeFilledIds.value.length)

export const dragPracticeBlankCount = computed(() => dragPracticeBlankIds.value.length)

/** Open setup chooser (always — does not touch 挖空支架图). */
export function openDragPractice(): void {
  if (!ensureAuthoringAllowed()) return
  const diagramStore = useDiagramSession()
  if (!diagramStore.data?.nodes?.length) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  if (dragPracticeActive.value || dragPracticePicking.value) {
    exitDragPractice()
  }
  dragPracticeSetupOpen.value = true
}

export function closeDragPracticeSetup(): void {
  dragPracticeSetupOpen.value = false
}

function applyBlankIds(nodeIds: string[]): void {
  const answers = snapshotAnswersForIds(nodeIds)
  dragPracticeBlankIds.value = Object.keys(answers)
  dragPracticeAnswers.value = answers
}

export function startDragPracticeFromRandom(): void {
  if (!ensureAuthoringAllowed()) return
  const diagramStore = useDiagramSession()
  const nodes = diagramStore.data?.nodes
  const diagramType = diagramStore.type
  if (!nodes?.length || !diagramType) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  const ids = pickLearningSheetRandomNodeIds(nodes, diagramType)
  applyBlankIds(ids)
  enterPlaySession()
}

export function startDragPracticeFromFullBlank(): void {
  if (!ensureAuthoringAllowed()) return
  const diagramStore = useDiagramSession()
  const nodes = diagramStore.data?.nodes
  const diagramType = diagramStore.type
  if (!nodes?.length || !diagramType) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  const ids = pickLearningSheetRandomNodeIds(nodes, diagramType, 1)
  applyBlankIds(ids)
  enterPlaySession()
}

export function startDragPracticeFromCustomPick(): void {
  if (!ensureAuthoringAllowed()) return
  const diagramStore = useDiagramSession()
  if (!diagramStore.data?.nodes?.length) {
    notify.warningKey('canvas.toolbar.createDiagramFirst')
    return
  }
  dragPracticeSetupOpen.value = false
  dragPracticeActive.value = false
  dragPracticePicking.value = true
  if (dragPracticeBlankIds.value.length === 0) {
    dragPracticeBlankIds.value = []
    dragPracticeAnswers.value = {}
  }
  notify.infoKey('canvas.dragPractice.pickThenStart')
}

export function startDragPracticeWithExistingBlanks(): boolean {
  if (!ensureAuthoringAllowed()) return false
  if (dragPracticeBlankIds.value.length === 0) {
    notify.warningKey('canvas.dragPractice.needBlanks')
    return false
  }
  return enterPlaySession()
}

export function cancelScheduledDragPracticePick(): void {
  if (pickTimer !== null) {
    clearTimeout(pickTimer)
    pickTimer = null
  }
  pickNodeId = null
}

export function scheduleDragPracticePickNodeClick(nodeId: string): boolean {
  if (!dragPracticePicking.value) return false
  cancelScheduledDragPracticePick()
  pickNodeId = nodeId
  pickTimer = setTimeout(() => {
    pickTimer = null
    const id = pickNodeId
    pickNodeId = null
    if (id) toggleDragPracticeBlank(id)
  }, PICK_CLICK_DELAY_MS)
  return true
}

export function toggleDragPracticeBlank(nodeId: string): void {
  if (!dragPracticePicking.value) return
  const diagramStore = useDiagramSession()
  if (isProtectedNodeId(nodeId, diagramStore)) {
    notify.warningKey('canvas.dragPractice.protectedNode')
    return
  }
  const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
  if (!node) return
  const text = nodeAnswerText(node)
  if (!text) {
    notify.warningKey('canvas.dragPractice.emptyNode')
    return
  }

  const selected = new Set(dragPracticeBlankIds.value)
  if (selected.has(nodeId)) {
    selected.delete(nodeId)
    const nextAnswers = { ...dragPracticeAnswers.value }
    delete nextAnswers[nodeId]
    dragPracticeAnswers.value = nextAnswers
  } else {
    selected.add(nodeId)
    dragPracticeAnswers.value = { ...dragPracticeAnswers.value, [nodeId]: text }
  }
  dragPracticeBlankIds.value = [...selected]
}

export function restartDragPractice(): void {
  if (!dragPracticeActive.value) return
  clearAllMarkTimers()
  dragPracticeChips.value = buildChipsFromBlanks()
  dragPracticeFilledIds.value = []
  dragPracticeUsedChipIds.value = []
  dragPracticeMarks.value = {}
  dragPracticeDraggingId.value = null
  notify.successKey('canvas.dragPractice.restarted')
}

export function exitDragPractice(): void {
  cancelScheduledDragPracticePick()
  clearAllMarkTimers()
  dragPracticeActive.value = false
  dragPracticeSetupOpen.value = false
  dragPracticePicking.value = false
  dragPracticeBlankIds.value = []
  dragPracticeAnswers.value = {}
  dragPracticeChips.value = []
  dragPracticeFilledIds.value = []
  dragPracticeUsedChipIds.value = []
  dragPracticeMarks.value = {}
  dragPracticeDraggingId.value = null
}

export function resetDragPracticeUi(): void {
  exitDragPractice()
}

function consumeDragPracticeChip(given: string, chipId?: string): void {
  const text = given.trim()
  const unused = (id: string) => !dragPracticeUsedChipIds.value.includes(id)
  const exact =
    chipId &&
    dragPracticeChips.value.find(
      (chip) => chip.id === chipId && chip.text.trim() === text && unused(chip.id)
    )
  const fallback = dragPracticeChips.value.find(
    (chip) => chip.text.trim() === text && unused(chip.id)
  )
  const chip = exact || fallback
  if (!chip) return
  dragPracticeUsedChipIds.value = [...dragPracticeUsedChipIds.value, chip.id]
}

export function dragPracticeDropOnNode(nodeId: string, given: string, chipId?: string): boolean {
  if (!dragPracticeActive.value) return false
  if (!dragPracticeBlankIds.value.includes(nodeId)) return false
  if (dragPracticeFilledIds.value.includes(nodeId)) return false

  const diagramStore = useDiagramSession()
  const nodes = diagramStore.data?.nodes ?? []
  const connections = diagramStore.data?.connections ?? []
  const group = dragPracticeSlotGroup(diagramStore.type, nodeId, nodes, connections)
  const text = given.trim()
  const matchId = dragPracticeBlankIds.value.find((id) => {
    if (dragPracticeFilledIds.value.includes(id)) return false
    if (dragPracticeSlotGroup(diagramStore.type, id, nodes, connections) !== group) return false
    return dragPracticeAnswers.value[id]?.trim() === text
  })
  const ok = Boolean(matchId)
  dragPracticeMarks.value = { ...dragPracticeMarks.value, [nodeId]: ok }
  scheduleMarkClear(nodeId, ok ? MARK_OK_MS : MARK_BAD_MS)
  if (!ok || !matchId) return false

  if (matchId !== nodeId) {
    const next = { ...dragPracticeAnswers.value }
    const placed = next[matchId]
    next[matchId] = next[nodeId]
    next[nodeId] = placed
    dragPracticeAnswers.value = next
  }
  consumeDragPracticeChip(text, chipId)
  dragPracticeFilledIds.value = [...dragPracticeFilledIds.value, nodeId]
  if (dragPracticeFilledIds.value.length >= dragPracticeBlankIds.value.length) {
    notify.successKey('canvas.dragPractice.allDone')
  }
  return true
}

export function noteDragPracticeWrongDrop(nodeId: string): void {
  if (!dragPracticeActive.value) return
  if (!dragPracticeBlankIds.value.includes(nodeId)) return
  if (dragPracticeFilledIds.value.includes(nodeId)) return
  dragPracticeMarks.value = { ...dragPracticeMarks.value, [nodeId]: false }
  scheduleMarkClear(nodeId, MARK_BAD_MS)
}

export function useDragPracticeKeyboard(): void {
  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape') return
    if (!dragPracticeActive.value && !dragPracticePicking.value && !dragPracticeSetupOpen.value) {
      return
    }
    const target = event.target as HTMLElement | null
    if (
      target?.tagName === 'INPUT' ||
      target?.tagName === 'TEXTAREA' ||
      target?.isContentEditable
    ) {
      return
    }
    event.preventDefault()
    exitDragPractice()
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
  })
}

export function useDragPractice() {
  return {
    active: dragPracticeActive,
    setupOpen: dragPracticeSetupOpen,
    picking: dragPracticePicking,
    blankIds: dragPracticeBlankIds,
    chips: dragPracticeChips,
    filledIds: dragPracticeFilledIds,
    marks: dragPracticeMarks,
    draggingId: dragPracticeDraggingId,
    remainingCount: dragPracticeRemainingCount,
    totalCount: dragPracticeTotalCount,
    correctCount: dragPracticeCorrectCount,
    blankCount: dragPracticeBlankCount,
    open: openDragPractice,
    closeSetup: closeDragPracticeSetup,
    startFromRandom: startDragPracticeFromRandom,
    startFromFullBlank: startDragPracticeFromFullBlank,
    startFromCustomPick: startDragPracticeFromCustomPick,
    startWithExistingBlanks: startDragPracticeWithExistingBlanks,
    restart: restartDragPractice,
    exit: exitDragPractice,
  }
}
