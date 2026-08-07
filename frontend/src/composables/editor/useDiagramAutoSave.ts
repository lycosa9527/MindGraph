/**
 * useDiagramAutoSave - Event-driven diagram auto-save workflow
 *
 * Centralizes save logic with:
 * - Config-driven timing (no hardcoded values)
 * - Event-based coordination (diagram:loaded_from_library, llm:model_completed,
 *   llm:generation_completed)
 * - State-driven guards (auth, isGenerating, suppress window); per-LLM-round saves
 *   bypass the generating guard so each model persists without waiting for slow peers
 * - Content fingerprint computed + watch (Vue deep watch gives same ref for
 *   in-place mutations; computed fingerprint yields proper old/new on change)
 * - Sync snapshot before the persist queue (leave/unmount must not race reset())
 * - Periodic interval save to catch position/style-only edits
 * - isDirty / isSaving flags for UI feedback
 *
 * Usage:
 *   const autoSave = useDiagramAutoSave({ getDiagramTitle, onSaved })
 *   // On canvas leave: flushOnLeave() → teardown() → reset Pinia → clearActiveDiagram in finally
 */
import { storeToRefs } from 'pinia'
import { type ComputedRef, computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { eventBus } from '@/composables'
import { SAVE } from '@/config'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'
import { resolveDiagramTitleForSave } from '@/utils/diagramTitleForSave'
import { mindMapLiveSpecExtrasFingerprint } from '@/utils/mindMapLiveSpecExtras'

import {
  canPerformDiagramSave,
  shouldAutoSaveAfterLlmModelCompleted,
} from './diagramSaveFeedback'
import { useLanguage } from '../core/useLanguage'
import { useDiagramSpecForPersist } from './useDiagramSpecForSave'

type DiagramDataLike = { nodes?: unknown[]; connections?: unknown[] } | null

interface NodeLike {
  id?: string
  text?: string
  data?: {
    label?: string
    hidden?: boolean
    hiddenAnswer?: string
    mindMapUid?: string
  }
  position?: { x?: number; y?: number }
  style?: unknown
}

type DiagramDataRecord = DiagramDataLike & {
  isLearningSheet?: boolean
  is_learning_sheet?: boolean
  learningSheetShowAnswers?: boolean
  learning_sheet_show_answers?: boolean
  hiddenAnswers?: string[]
}

function learningSheetFingerprint(data: DiagramDataLike): string {
  if (!data) return ''
  const record = data as DiagramDataRecord
  const nodes = data.nodes || []
  const blankedNodes = nodes
    .map((n) => {
      const node = n as NodeLike
      return JSON.stringify({
        id: node.id,
        hidden: node.data?.hidden === true,
        hiddenAnswer: node.data?.hiddenAnswer ?? '',
      })
    })
    .sort()
  return JSON.stringify({
    isLearningSheet:
      record.isLearningSheet === true || record.is_learning_sheet === true,
    showAnswers: !(
      record.learningSheetShowAnswers === false ||
      record.learning_sheet_show_answers === false
    ),
    hiddenAnswers: Array.isArray(record.hiddenAnswers) ? [...record.hiddenAnswers].sort() : [],
    blankedNodes,
  })
}

interface ConnectionLike {
  id?: string
  source?: string
  target?: string
  label?: string
  arrowheadDirection?: string
}

function getContentFingerprint(data: DiagramDataLike): string {
  if (!data) return ''
  const nodes = data.nodes || []
  const conns = data.connections || []
  const nodeContent = (n: unknown) => {
    const node = n as NodeLike
    return JSON.stringify({
      id: node.id,
      text: node.text ?? node.data?.label ?? '',
      hidden: node.data?.hidden === true,
      hiddenAnswer: node.data?.hiddenAnswer ?? '',
      // First layout assigns mindMapUid without text changes — must autosave.
      mindMapUid: node.data?.mindMapUid ?? '',
    })
  }
  const connContent = (c: unknown) => {
    const conn = c as ConnectionLike
    return JSON.stringify({
      id: conn.id,
      source: conn.source,
      target: conn.target,
      label: conn.label,
      arrowheadDirection: conn.arrowheadDirection,
    })
  }
  const nodeFingerprints = nodes.map(nodeContent).sort()
  const connFingerprints = conns.map(connContent).sort()
  return JSON.stringify({
    nodes: nodeFingerprints,
    conns: connFingerprints,
    learningSheet: learningSheetFingerprint(data),
    // Theme / collapse / style-only mindmap edits must debounce-save to library.
    mindMapExtras: mindMapLiveSpecExtrasFingerprint(data as Record<string, unknown>),
  })
}

function getFullFingerprint(data: DiagramDataLike): string {
  if (!data) return ''
  const nodes = data.nodes || []
  const conns = data.connections || []
  const nodeFull = (n: unknown) => {
    const node = n as NodeLike
    const posKey = node.position
      ? `${Math.round(node.position.x ?? 0)},${Math.round(node.position.y ?? 0)}`
      : ''
    return JSON.stringify({
      id: node.id,
      text: node.text ?? node.data?.label ?? '',
      hidden: node.data?.hidden === true,
      hiddenAnswer: node.data?.hiddenAnswer ?? '',
      pos: posKey,
      style: node.style ?? null,
    })
  }
  const connFull = (c: unknown) => {
    const conn = c as ConnectionLike
    return JSON.stringify({
      id: conn.id,
      source: conn.source,
      target: conn.target,
      label: conn.label,
      arrowheadDirection: conn.arrowheadDirection,
    })
  }
  const nodeFingerprints = nodes.map(nodeFull).sort()
  const connFingerprints = conns.map(connFull).sort()
  return JSON.stringify({
    nodes: nodeFingerprints,
    conns: connFingerprints,
    learningSheet: learningSheetFingerprint(data),
  })
}

export interface SaveFlushResult {
  saved: boolean
  reason?: 'success' | 'skipped_guards' | 'skipped_slots_full' | 'skipped_empty' | 'error'
}

export interface UseDiagramAutoSaveOptions {
  getDiagramTitle?: () => string
  onSaved?: (result: { action: string; diagramId?: string }) => void
  isCollabGuest?: ComputedRef<boolean>
  /**
   * True while the diagram is locked inside an active workshop/collab session.
   * Blocks the host's autosave REST PUT (which the server rejects with 409
   * while the session is live). Changes are persisted through the WebSocket
   * collab pipeline instead; autosave re-enables automatically when the session
   * ends and the flag returns to false.
   */
  isCollabActive?: ComputedRef<boolean>
}

type SaveAttemptOptions = {
  bypassGeneratingGuard?: boolean
  bypassSubgraphGuard?: boolean
  bypassSuppressGuard?: boolean
}

type CapturedSave = {
  title: string
  diagramType: string
  spec: Record<string, unknown>
  language: string
  editCount: number
  fullFingerprint: string
  /** Library row id at capture time (survive clearActiveDiagram during leave). */
  targetDiagramId: string | null
}

export function useDiagramAutoSave(options: UseDiagramAutoSaveOptions = {}) {
  const router = useRouter()
  const route = useRoute()
  const { promptLanguage, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const authStore = useAuthStore()
  const previewStore = useMindMapSubgraphPreviewStore()
  const { isGenerating: isSubgraphGenerating } = storeToRefs(previewStore)
  const getDiagramSpecForPersist = useDiagramSpecForPersist()

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let intervalTimer: ReturnType<typeof setInterval> | null = null
  let suppressTimer: ReturnType<typeof setTimeout> | null = null
  const isSuppressed = ref(false)
  const lastSavedAt = ref<Date | null>(null)
  const isDirty = ref(false)
  const isSaving = ref(false)
  let disposed = false

  let lastSavedFullFingerprint = ''
  let consecutiveSaveFailures = 0
  const MAX_CONSECUTIVE_SAVE_FAILURES = 3
  let persistQueue: Promise<SaveFlushResult> = Promise.resolve({
    saved: false,
    reason: 'skipped_guards',
  })

  const diagramTypeForName = computed(
    () => (diagramStore.type as string) || (route.query.type as string) || null
  )

  function getTitle(): string {
    if (options.getDiagramTitle) return options.getDiagramTitle()
    return resolveDiagramTitleForSave(
      diagramStore.effectiveTitle,
      diagramTypeForName.value,
      currentLanguage.value
    )
  }

  function buildSaveEligibility(saveOpts: SaveAttemptOptions = {}) {
    return {
      authenticated:
        authStore.isAuthenticated && !authStore.authVerificationBlockedByNetwork,
      llmGenerating: llmResultsStore.isGenerating,
      subgraphGenerating: isSubgraphGenerating.value,
      suppressed: isSuppressed.value,
      isCollabGuest: Boolean(options.isCollabGuest?.value),
      collabSessionActive: Boolean(options.isCollabActive?.value),
      hasTypeAndData: Boolean(diagramStore.type && diagramStore.data),
      bypassGeneratingGuard: saveOpts.bypassGeneratingGuard === true,
      bypassSubgraphGuard: saveOpts.bypassSubgraphGuard === true,
      bypassSuppressGuard: saveOpts.bypassSuppressGuard === true,
    }
  }

  const canSave = computed(() => canPerformDiagramSave(buildSaveEligibility()))

  function cancelDebounce(): void {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
  }

  function startInterval(): void {
    if (intervalTimer) return
    intervalTimer = setInterval(() => {
      if (!canSave.value || !isDirty.value) return
      const currentFull = getFullFingerprint(diagramStore.data as DiagramDataLike)
      if (currentFull === lastSavedFullFingerprint) {
        isDirty.value = false
        return
      }
      void performSave()
    }, SAVE.MAX_SAVE_INTERVAL_MS)
  }

  function stopInterval(): void {
    if (intervalTimer) {
      clearInterval(intervalTimer)
      intervalTimer = null
    }
  }

  function captureSaveAttempt(
    saveOpts: SaveAttemptOptions = {}
  ): { ok: true; captured: CapturedSave } | { ok: false; result: SaveFlushResult } {
    if (!canPerformDiagramSave(buildSaveEligibility(saveOpts))) {
      return { ok: false, result: { saved: false, reason: 'skipped_guards' } }
    }
    if (consecutiveSaveFailures >= MAX_CONSECUTIVE_SAVE_FAILURES) {
      return { ok: false, result: { saved: false, reason: 'error' } }
    }

    const spec = getDiagramSpecForPersist()
    if (!spec) return { ok: false, result: { saved: false, reason: 'skipped_empty' } }

    const diagramType = diagramStore.type
    if (!diagramType) return { ok: false, result: { saved: false, reason: 'skipped_empty' } }

    return {
      ok: true,
      captured: {
        title: getTitle(),
        diagramType,
        spec,
        language: promptLanguage.value,
        editCount: diagramStore.sessionEditCount,
        fullFingerprint: getFullFingerprint(diagramStore.data as DiagramDataLike),
        targetDiagramId: savedDiagramsStore.activeDiagramId,
      },
    }
  }

  async function performSaveInternal(captured: CapturedSave): Promise<SaveFlushResult> {
    isSaving.value = true
    try {
      const result = await savedDiagramsStore.autoSaveDiagram(
        captured.title,
        captured.diagramType,
        captured.spec,
        captured.language,
        null,
        captured.editCount,
        captured.targetDiagramId
      )

      if (result.success) {
        consecutiveSaveFailures = 0
        lastSavedAt.value = new Date()
        lastSavedFullFingerprint = captured.fullFingerprint
        diagramStore.resetSessionEditCount()

        const currentFull = getFullFingerprint(diagramStore.data as DiagramDataLike)
        if (!diagramStore.data || currentFull === captured.fullFingerprint) {
          isDirty.value = false
        } else {
          // Newer edits landed after this snapshot — keep dirty and reschedule.
          isDirty.value = true
          if (!disposed) trigger()
        }

        if (!disposed) {
          options.onSaved?.({
            action: result.action,
            diagramId: result.diagramId,
          })
          if (result.action === 'saved' && result.diagramId) {
            const canvasPath = canvasEditorPathForRoute(route.path)
            const currentId = route.query.diagramId
            if (String(currentId ?? '') !== String(result.diagramId)) {
              router.replace({ path: canvasPath, query: { diagramId: result.diagramId } })
            }
          }
        }
        return { saved: true, reason: 'success' }
      }

      if (result.action === 'skipped' && result.error === 'No available slots') {
        return { saved: false, reason: 'skipped_slots_full' }
      }
      if (!authStore.isAuthenticated) {
        cancelDebounce()
        isDirty.value = false
        return { saved: false, reason: 'skipped_guards' }
      }
      consecutiveSaveFailures += 1
      if (consecutiveSaveFailures >= MAX_CONSECUTIVE_SAVE_FAILURES) {
        cancelDebounce()
      }
      return { saved: false, reason: 'error' }
    } catch (error) {
      console.error('[useDiagramAutoSave] Save error:', error)
      consecutiveSaveFailures += 1
      if (consecutiveSaveFailures >= MAX_CONSECUTIVE_SAVE_FAILURES) {
        cancelDebounce()
      }
      return { saved: false, reason: 'error' }
    } finally {
      isSaving.value = false
    }
  }

  function performSave(saveOpts: SaveAttemptOptions = {}): Promise<SaveFlushResult> {
    // Snapshot before persistQueue microtask so leave/reset cannot clear Pinia first.
    const attempt = captureSaveAttempt(saveOpts)
    if (!attempt.ok) return Promise.resolve(attempt.result)
    const next = persistQueue.then(() => performSaveInternal(attempt.captured))
    persistQueue = next.catch((): SaveFlushResult => ({ saved: false, reason: 'error' }))
    return next
  }

  function trigger(): void {
    if (disposed) return
    cancelDebounce()
    consecutiveSaveFailures = 0
    isDirty.value = true
    debounceTimer = setTimeout(() => {
      void performSave()
    }, SAVE.AUTO_SAVE_DEBOUNCE_MS)
  }

  /**
   * Immediate persist. Default bypasses subgraph busy (paste already applied).
   * Pass leave-style bypasses from canvas unmount so suppress/LLM cannot drop the snapshot.
   */
  async function flush(saveOpts: SaveAttemptOptions = {}): Promise<SaveFlushResult> {
    cancelDebounce()
    if (!authStore.isAuthenticated) {
      return { saved: false, reason: 'skipped_guards' }
    }
    if (!savedDiagramsStore.activeDiagramId && savedDiagramsStore.isSlotsFullyUsed) {
      return { saved: false, reason: 'skipped_slots_full' }
    }
    return performSave({
      bypassSubgraphGuard: true,
      ...saveOpts,
    })
  }

  /** Canvas leave: persist even while suppress / LLM / subgraph flags are still set. */
  async function flushOnLeave(): Promise<SaveFlushResult> {
    return flush({
      bypassSubgraphGuard: true,
      bypassSuppressGuard: true,
      bypassGeneratingGuard: true,
    })
  }

  const contentFingerprint = computed(() =>
    getContentFingerprint(diagramStore.data as DiagramDataLike)
  )

  function markDirtyIfAheadOfLastSave(): void {
    if (disposed || !diagramStore.data) return
    const currentFull = getFullFingerprint(diagramStore.data as DiagramDataLike)
    if (!currentFull || currentFull === lastSavedFullFingerprint) return
    trigger()
  }

  const stopContentWatch = watch(contentFingerprint, (newFP, oldFP) => {
    if (!newFP || oldFP === undefined || newFP === oldFP) return
    if (llmResultsStore.contentChangeIsFromModelSwitch) {
      llmResultsStore.contentChangeIsFromModelSwitch = false
      cancelDebounce()
      return
    }
    if (!llmResultsStore.isGenerating && !isSuppressed.value) {
      trigger()
      return
    }
    // Suppress / LLM stream: remember dirty so end-of-suppress / canSave retry can flush.
    isDirty.value = true
  })

  const stopTitleWatch = watch(
    () => (diagramStore.isUserEditedTitle ? diagramStore.title : null),
    (newTitle, oldTitle) => {
      if (!diagramStore.isUserEditedTitle) return
      if (oldTitle === undefined || newTitle === oldTitle) return
      if (!newTitle?.trim() && !oldTitle?.trim()) return
      trigger()
    }
  )

  function setSuppressWindow(ms: number): void {
    if (suppressTimer) clearTimeout(suppressTimer)
    isSuppressed.value = true
    suppressTimer = setTimeout(() => {
      isSuppressed.value = false
      suppressTimer = null
      markDirtyIfAheadOfLastSave()
    }, ms)
  }

  function setSuppressFromLibrary(): void {
    cancelDebounce()
    isDirty.value = false
    lastSavedFullFingerprint = getFullFingerprint(diagramStore.data as DiagramDataLike)
    setSuppressWindow(SAVE.SUPPRESS_AFTER_LOAD_MS)
  }

  const stopIsGenerating = watch(
    () => llmResultsStore.isGenerating,
    (isGen) => {
      if (isGen) cancelDebounce()
    }
  )

  // Debounce often hits skipped_guards while subgraph is busy; retry when idle + dirty.
  const stopCanSaveWatch = watch(canSave, (ok) => {
    if (!ok || !isDirty.value || isSaving.value || disposed) return
    void performSave()
  })

  const stopLlmModelCompleted = eventBus.on(
    'llm:model_completed',
    (data: { success?: boolean }) => {
      if (shouldAutoSaveAfterLlmModelCompleted(data.success)) {
        void performSave({ bypassGeneratingGuard: true })
      }
    }
  )

  const stopLlmComplete = eventBus.on(
    'llm:generation_completed',
    (data: { allFailed?: boolean }) => {
      if (!data.allFailed) {
        void flush()
      }
    }
  )

  const stopLoadedFromLibrary = eventBus.on('diagram:loaded_from_library', () =>
    setSuppressFromLibrary()
  )

  const stopWorkshopSnapshot = eventBus.on('diagram:workshop_snapshot_applied', () => {
    setSuppressWindow(SAVE.SUPPRESS_AFTER_WORKSHOP_SNAPSHOT_MS)
  })

  const stopOperationCompleted = eventBus.on(
    'diagram:operation_completed',
    (payload: { operation?: string }) => {
      if (payload?.operation === 'move_branch') trigger()
    }
  )

  const stopPositionChanged = eventBus.on('diagram:position_changed', () => {
    isDirty.value = true
  })

  const stopStyleChanged = eventBus.on('diagram:style_changed', () => {
    isDirty.value = true
  })

  const stopLearningSheetChanged = eventBus.on('diagram:learning_sheet_changed', () => {
    trigger()
  })

  startInterval()

  function teardown(): void {
    disposed = true
    cancelDebounce()
    stopInterval()
    if (suppressTimer) {
      clearTimeout(suppressTimer)
      suppressTimer = null
    }
    stopContentWatch()
    stopTitleWatch()
    stopIsGenerating()
    stopCanSaveWatch()
    stopLlmModelCompleted()
    stopLlmComplete()
    stopLoadedFromLibrary()
    stopWorkshopSnapshot()
    stopOperationCompleted()
    stopPositionChanged()
    stopStyleChanged()
    stopLearningSheetChanged()
  }

  // Pages own teardown after flushOnLeave (see CanvasPage / MobileCanvasPage).
  // Auto onUnmounted would run before the page leave hook and race capture.

  return {
    trigger,
    flush,
    flushOnLeave,
    performSave,
    setSuppressFromLibrary,
    cancelTimer: cancelDebounce,
    teardown,
    lastSavedAt,
    isDirty,
    isSaving,
  }
}
