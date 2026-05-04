/**
 * useDiagramAutoSave - Event-driven diagram auto-save workflow
 *
 * Centralizes save logic with:
 * - Config-driven timing (no hardcoded values)
 * - Event-based coordination (diagram:loaded_from_library, llm:generation_completed)
 * - State-driven guards (auth, isGenerating, suppress window)
 * - Content fingerprint computed + watch (Vue deep watch gives same ref for
 *   in-place mutations; computed fingerprint yields proper old/new on change)
 * - Periodic interval save to catch position/style-only edits
 * - isDirty / isSaving flags for UI feedback
 *
 * Usage:
 *   const autoSave = useDiagramAutoSave({ getDiagramTitle, onSaved })
 *   // Composable sets up internal watch; no CanvasPage integration needed
 *   // On unmount: autoSave.teardown()
 */
import { type ComputedRef, computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { eventBus, getDefaultDiagramName } from '@/composables'
import { SAVE } from '@/config'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'

import { useLanguage } from '../core/useLanguage'
import { useDiagramSpecForSave } from './useDiagramSpecForSave'

type DiagramDataLike = { nodes?: unknown[]; connections?: unknown[] } | null

interface NodeLike {
  id?: string
  text?: string
  data?: { label?: string }
  position?: { x?: number; y?: number }
  style?: unknown
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
  return JSON.stringify({ nodes: nodeFingerprints, conns: connFingerprints })
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
  return JSON.stringify({ nodes: nodeFingerprints, conns: connFingerprints })
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

export function useDiagramAutoSave(options: UseDiagramAutoSaveOptions = {}) {
  const router = useRouter()
  const route = useRoute()
  const { promptLanguage, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const authStore = useAuthStore()
  const getDiagramSpec = useDiagramSpecForSave()

  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let intervalTimer: ReturnType<typeof setInterval> | null = null
  let suppressTimer: ReturnType<typeof setTimeout> | null = null
  const isSuppressed = ref(false)
  const lastSavedAt = ref<Date | null>(null)
  const isDirty = ref(false)
  const isSaving = ref(false)

  let lastSavedFullFingerprint = ''

  const diagramTypeForName = computed(
    () => (diagramStore.type as string) || (route.query.type as string) || null
  )

  function getTitle(): string {
    if (options.getDiagramTitle) return options.getDiagramTitle()
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) return topicText
    return (
      diagramStore.effectiveTitle ||
      getDefaultDiagramName(diagramTypeForName.value, currentLanguage.value)
    )
  }

  const canSave = computed(
    () =>
      authStore.isAuthenticated &&
      !llmResultsStore.isGenerating &&
      !isSuppressed.value &&
      !options.isCollabGuest?.value &&
      !options.isCollabActive?.value &&
      !!diagramStore.type &&
      !!diagramStore.data
  )

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
      performSave()
    }, SAVE.MAX_SAVE_INTERVAL_MS)
  }

  function stopInterval(): void {
    if (intervalTimer) {
      clearInterval(intervalTimer)
      intervalTimer = null
    }
  }

  async function performSave(): Promise<SaveFlushResult> {
    if (!canSave.value) return { saved: false, reason: 'skipped_guards' }

    const base = diagramStore.getSpecForSave()
    if (base) llmResultsStore.updateCurrentModelSpec(base)
    const spec = getDiagramSpec()
    if (!spec) return { saved: false, reason: 'skipped_empty' }

    const diagramType = diagramStore.type
    if (!diagramType) return { saved: false, reason: 'skipped_empty' }

    isSaving.value = true
    try {
      const result = await savedDiagramsStore.autoSaveDiagram(
        getTitle(),
        diagramType,
        spec,
        promptLanguage.value,
        null,
        diagramStore.sessionEditCount
      )

      if (result.success) {
        lastSavedAt.value = new Date()
        lastSavedFullFingerprint = getFullFingerprint(diagramStore.data as DiagramDataLike)
        isDirty.value = false
        diagramStore.resetSessionEditCount()
        llmResultsStore.updateCurrentModelSpec(spec)
        options.onSaved?.({
          action: result.action,
          diagramId: result.diagramId,
        })
        if (result.action === 'saved' && result.diagramId) {
          const canvasPath = canvasEditorPathForRoute(route.path)
          router.replace({ path: canvasPath, query: { diagramId: result.diagramId } })
        }
        return { saved: true, reason: 'success' }
      }

      if (result.action === 'skipped' && result.error === 'No available slots') {
        return { saved: false, reason: 'skipped_slots_full' }
      }
      return { saved: false, reason: 'error' }
    } catch (error) {
      console.error('[useDiagramAutoSave] Save error:', error)
      return { saved: false, reason: 'error' }
    } finally {
      isSaving.value = false
    }
  }

  function trigger(): void {
    cancelDebounce()
    isDirty.value = true
    debounceTimer = setTimeout(performSave, SAVE.AUTO_SAVE_DEBOUNCE_MS)
  }

  async function flush(): Promise<SaveFlushResult> {
    cancelDebounce()
    if (!authStore.isAuthenticated) {
      return { saved: false, reason: 'skipped_guards' }
    }
    if (!savedDiagramsStore.activeDiagramId && savedDiagramsStore.isSlotsFullyUsed) {
      return { saved: false, reason: 'skipped_slots_full' }
    }
    return performSave()
  }

  const contentFingerprint = computed(() =>
    getContentFingerprint(diagramStore.data as DiagramDataLike)
  )

  const stopContentWatch = watch(contentFingerprint, (newFP, oldFP) => {
    if (!newFP || oldFP === undefined || newFP === oldFP) return
    if (llmResultsStore.contentChangeIsFromModelSwitch) {
      llmResultsStore.contentChangeIsFromModelSwitch = false
      cancelDebounce()
      return
    }
    if (!llmResultsStore.isGenerating && !isSuppressed.value) trigger()
  })

  function setSuppressWindow(ms: number): void {
    if (suppressTimer) clearTimeout(suppressTimer)
    isSuppressed.value = true
    suppressTimer = setTimeout(() => {
      isSuppressed.value = false
      suppressTimer = null
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

  const stopLlmComplete = eventBus.on(
    'llm:generation_completed',
    (data: { allFailed?: boolean }) => {
      if (!data.allFailed) flush()
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

  startInterval()

  function teardown(): void {
    cancelDebounce()
    stopInterval()
    if (suppressTimer) {
      clearTimeout(suppressTimer)
      suppressTimer = null
    }
    stopContentWatch()
    stopIsGenerating()
    stopLlmComplete()
    stopLoadedFromLibrary()
    stopWorkshopSnapshot()
    stopOperationCompleted()
    stopPositionChanged()
    stopStyleChanged()
  }

  onUnmounted(teardown)

  return {
    trigger,
    flush,
    performSave,
    setSuppressFromLibrary,
    cancelTimer: cancelDebounce,
    teardown,
    lastSavedAt,
    isDirty,
    isSaving,
  }
}
