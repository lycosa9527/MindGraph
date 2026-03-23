/**
 * useDiagramAutoSave - Event-driven diagram auto-save workflow
 *
 * Centralizes save logic with:
 * - Config-driven timing (no hardcoded values)
 * - Event-based coordination (diagram:loaded_from_library, llm:generation_completed)
 * - State-driven guards (auth, isGenerating, suppress window)
 * - Content fingerprint computed + watch (Vue deep watch gives same ref for
 *   in-place mutations; computed fingerprint yields proper old/new on change)
 *
 * Usage:
 *   const autoSave = useDiagramAutoSave({ getDiagramTitle, onSaved })
 *   // Composable sets up internal watch; no CanvasPage integration needed
 *   // On unmount: autoSave.teardown()
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { eventBus, getDefaultDiagramName } from '@/composables'
import { SAVE } from '@/config'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

import { useDiagramSpecForSave } from './useDiagramSpecForSave'
import { useLanguage } from './useLanguage'

type DiagramDataLike = { nodes?: unknown[]; connections?: unknown[] } | null

function getContentFingerprint(data: DiagramDataLike): string {
  if (!data) return ''
  const nodes = data.nodes || []
  const conns = data.connections || []
  const nodeContent = (n: unknown) => {
    const node = n as { id?: string; text?: string; data?: { label?: string } }
    return JSON.stringify({
      id: node.id,
      text: node.text ?? node.data?.label ?? '',
    })
  }
  const connContent = (c: unknown) => {
    const conn = c as {
      id?: string
      source?: string
      target?: string
      label?: string
      arrowheadDirection?: string
    }
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

export interface UseDiagramAutoSaveOptions {
  getDiagramTitle?: () => string
  onSaved?: (result: { action: string; diagramId?: string }) => void
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

  let timer: ReturnType<typeof setTimeout> | null = null
  const suppressUntil = ref(0)
  const lastSavedAt = ref<Date | null>(null)

  const diagramTypeForName = computed(
    () => (diagramStore.type as string) || (route.query.type as string) || null
  )

  function getTitle(): string {
    if (options.getDiagramTitle) return options.getDiagramTitle()
    const topicText = diagramStore.getTopicNodeText()
    if (topicText) return topicText
    return (
      diagramStore.effectiveTitle || getDefaultDiagramName(diagramTypeForName.value, currentLanguage.value)
    )
  }

  const isSuppressed = computed(() => Date.now() < suppressUntil.value)

  const canSave = computed(
    () =>
      authStore.isAuthenticated &&
      !llmResultsStore.isGenerating &&
      !isSuppressed.value &&
      !!diagramStore.type &&
      !!diagramStore.data
  )

  function cancelTimer(): void {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  async function performSave(): Promise<void> {
    if (!canSave.value) return

    const base = diagramStore.getSpecForSave()
    if (base) llmResultsStore.updateCurrentModelSpec(base)
    const spec = getDiagramSpec()
    if (!spec) return

    const diagramType = diagramStore.type
    if (!diagramType) return

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
        diagramStore.resetSessionEditCount()
        llmResultsStore.updateCurrentModelSpec(spec)
        options.onSaved?.({
          action: result.action,
          diagramId: result.diagramId,
        })
        if (result.action === 'saved' && result.diagramId) {
          router.replace({ path: '/canvas', query: { diagramId: result.diagramId } })
        }
      }
    } catch (error) {
      console.error('[useDiagramAutoSave] Save error:', error)
    }
  }

  function trigger(): void {
    cancelTimer()
    timer = setTimeout(performSave, SAVE.AUTO_SAVE_DEBOUNCE_MS)
  }

  function flush(): void {
    cancelTimer()
    performSave()
  }

  const contentFingerprint = computed(() =>
    getContentFingerprint(diagramStore.data as DiagramDataLike)
  )

  const stopContentWatch = watch(contentFingerprint, (newFP, oldFP) => {
    if (!newFP || oldFP === undefined || newFP === oldFP) return
    // Content change from model switch: save-before-replace already saved user edits.
    // Do not overwrite with the new model's result. Cancel any pending save.
    if (llmResultsStore.contentChangeIsFromModelSwitch) {
      llmResultsStore.contentChangeIsFromModelSwitch = false
      cancelTimer()
      return
    }
    if (!llmResultsStore.isGenerating && !isSuppressed.value) trigger()
  })

  function setSuppressFromLibrary(): void {
    cancelTimer()
    suppressUntil.value = Date.now() + SAVE.SUPPRESS_AFTER_LOAD_MS
  }

  const stopIsGenerating = watch(
    () => llmResultsStore.isGenerating,
    (isGen) => {
      if (isGen) cancelTimer()
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
    suppressUntil.value = Date.now() + SAVE.SUPPRESS_AFTER_WORKSHOP_SNAPSHOT_MS
  })

  const stopOperationCompleted = eventBus.on(
    'diagram:operation_completed',
    (payload: { operation?: string }) => {
      if (payload?.operation === 'move_branch') trigger()
    }
  )

  function teardown(): void {
    cancelTimer()
    stopContentWatch()
    stopIsGenerating()
    stopLlmComplete()
    stopLoadedFromLibrary()
    stopWorkshopSnapshot()
    stopOperationCompleted()
  }

  onUnmounted(teardown)

  return {
    trigger,
    flush,
    performSave,
    setSuppressFromLibrary,
    cancelTimer,
    teardown,
    lastSavedAt,
  }
}
