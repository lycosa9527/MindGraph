/**
 * useDiagramAutoSave - Event-driven diagram auto-save workflow
 *
 * Centralizes save logic with:
 * - Config-driven timing (no hardcoded values)
 * - Event-based coordination (diagram:loaded_from_library, llm:generation_completed)
 * - State-driven guards (auth, isGenerating, suppress window)
 *
 * Usage:
 *   const autoSave = useDiagramAutoSave({ getDiagramTitle, onSaved })
 *   // In watch on diagramStore.data:
 *   if (autoSave.shouldTrigger(oldData, newData)) autoSave.trigger()
 *   // On unmount: autoSave.teardown()
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { SAVE } from '@/config'
import { eventBus, getDefaultDiagramName } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { useDiagramStore } from '@/stores/diagram'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useDiagramSpecForSave } from './useDiagramSpecForSave'
import { useLanguage } from './useLanguage'

function hasContentChange(
  oldData: { nodes?: unknown[]; connections?: unknown[] } | null,
  newData: { nodes?: unknown[]; connections?: unknown[] } | null
): boolean {
  if (!oldData || !newData) return false
  const oldNodes = oldData.nodes || []
  const newNodes = newData.nodes || []
  const oldConns = oldData.connections || []
  const newConns = newData.connections || []

  if (oldNodes.length !== newNodes.length) return true
  if (oldConns.length !== newConns.length) return true

  const nodeContent = (n: unknown) => {
    const node = n as { id?: string; text?: string; data?: { label?: string } }
    return JSON.stringify({
      id: node.id,
      text: node.text ?? node.data?.label ?? '',
    })
  }
  for (let i = 0; i < newNodes.length; i++) {
    const oldItem = oldNodes.find(
      (o) => (o as { id?: string }).id === (newNodes[i] as { id?: string }).id
    )
    if (!oldItem || nodeContent(oldItem) !== nodeContent(newNodes[i])) return true
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
  const oldConnKeys = new Set(oldConns.map(connContent))
  const newConnKeys = new Set(newConns.map(connContent))
  if (oldConnKeys.size !== newConnKeys.size) return true
  for (const k of newConnKeys) {
    if (!oldConnKeys.has(k)) return true
  }
  return false
}

export interface UseDiagramAutoSaveOptions {
  getDiagramTitle?: () => string
  onSaved?: (result: { action: string; diagramId?: string }) => void
}

export function useDiagramAutoSave(options: UseDiagramAutoSaveOptions = {}) {
  const router = useRouter()
  const route = useRoute()
  const { isZh } = useLanguage()
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
      diagramStore.effectiveTitle ||
      getDefaultDiagramName(diagramTypeForName.value, isZh.value)
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

    const spec = getDiagramSpec()
    if (!spec) return

    try {
      const result = await savedDiagramsStore.autoSaveDiagram(
        getTitle(),
        diagramStore.type!,
        spec,
        isZh.value ? 'zh' : 'en',
        null,
        diagramStore.sessionEditCount
      )

      if (result.success) {
        lastSavedAt.value = new Date()
        diagramStore.resetSessionEditCount()
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

  function shouldTrigger(
    oldData: { nodes?: unknown[]; connections?: unknown[] } | null,
    newData: { nodes?: unknown[]; connections?: unknown[] } | null
  ): boolean {
    return (
      hasContentChange(oldData, newData) &&
      !llmResultsStore.isGenerating &&
      !isSuppressed.value
    )
  }

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

  const stopLoadedFromLibrary = eventBus.on(
    'diagram:loaded_from_library',
    () => setSuppressFromLibrary()
  )

  function teardown(): void {
    cancelTimer()
    stopIsGenerating()
    stopLlmComplete()
    stopLoadedFromLibrary()
  }

  onUnmounted(teardown)

  return {
    shouldTrigger,
    trigger,
    flush,
    performSave,
    setSuppressFromLibrary,
    cancelTimer,
    teardown,
    lastSavedAt,
  }
}
