/**
 * Stream three educational panels for a mind map node in parallel.
 */
import { onUnmounted, ref, watch } from 'vue'

import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { useSavedDiagramsStore } from '@/stores'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'
import { collectMindMapExplainContext } from '@/utils/mindMapExplainContext'
import { consumeSseDataLines } from '@/utils/mindMateSseStream'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type MindMapNodeExplainTarget = {
  nodeId: string
  nodeLabel: string
}

export type MindMapExplainFacet = 'meaning' | 'conflict' | 'questions'

export type MindMapExplainPanel = {
  facet: MindMapExplainFacet
  text: string
  streaming: boolean
  error: string | null
}

const EXPLAIN_FACETS: MindMapExplainFacet[] = ['meaning', 'conflict', 'questions']

function normalizeDiagramType(type: DiagramType | null): string {
  if (!type) return 'mindmap'
  return type === 'mind_map' ? 'mindmap' : type
}

function emptyPanels(): MindMapExplainPanel[] {
  return EXPLAIN_FACETS.map((facet) => ({
    facet,
    text: '',
    streaming: false,
    error: null,
  }))
}

function formatHttpErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = (item as { msg?: unknown }).msg
          return typeof msg === 'string' ? msg : ''
        }
        return ''
      })
      .filter(Boolean)
    if (parts.length > 0) return parts.join('; ')
  }
  return fallback
}

export function useMindMapNodeExplain() {
  const { promptLanguage, t } = useLanguage()
  const notify = useNotifications()
  const diagramStore = useDiagramSession()
  const savedDiagramsStore = useSavedDiagramsStore()

  const visible = ref(false)
  const target = ref<MindMapNodeExplainTarget | null>(null)
  const panels = ref<MindMapExplainPanel[]>(emptyPanels())
  const loading = ref(false)
  const abortController = ref<AbortController | null>(null)
  /** Monotonic run id — ignore late writes from aborted generations. */
  const activeRunId = ref(0)

  function resolveNodeLabel(nodeId: string): string {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    return (node?.text ?? '').trim()
  }

  function buildExplainPayload(
    nodeId: string,
    nodeLabel: string,
    facet: MindMapExplainFacet,
    explainSessionId: string
  ) {
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    const ctx = collectMindMapExplainContext(nodes, connections, nodeId)
    const topicNode = nodes.find((n) => n.id === 'topic')
    const fallbackTopic = (topicNode?.text ?? diagramStore.effectiveTitle ?? '').trim()

    return {
      session_id: explainSessionId,
      node_id: nodeId,
      node_label: nodeLabel,
      topic: ctx?.topic || fallbackTopic,
      diagram_type: normalizeDiagramType(diagramStore.type),
      facet,
      top_level_branches: ctx?.topLevelBranches ?? [],
      ancestor_path: ctx?.ancestorPath ?? [],
      sibling_branches: ctx?.siblingBranches ?? [],
      child_branches: ctx?.childBranches ?? [],
      language: promptLanguage.value,
      diagram_id: savedDiagramsStore.activeDiagramId ?? undefined,
    }
  }

  function panelForRun(runId: number, facet: MindMapExplainFacet): MindMapExplainPanel | null {
    if (activeRunId.value !== runId) return null
    return panels.value.find((panel) => panel.facet === facet) ?? null
  }

  /** Abort in-flight streams and drop panel/session state (idempotent). */
  function clearSession(): void {
    abortController.value?.abort()
    abortController.value = null
    activeRunId.value += 1
    target.value = null
    panels.value = emptyPanels()
    loading.value = false
  }

  function close(): void {
    clearSession()
    visible.value = false
  }

  function notifyRunError(runId: number, message: string, errorType?: string): void {
    if (activeRunId.value !== runId) return
    if (errorType === 'thinking_coin_insufficient') {
      eventBus.emit('thinking_coins:insufficient', {})
    }
    notify.error(message || t('canvas.mindMapNodeExplain.requestFailed'))
  }

  async function streamFacet(
    runId: number,
    facet: MindMapExplainFacet,
    payload: Record<string, unknown>,
    signal: AbortSignal,
    onCrossCuttingError: (message: string, errorType?: string) => void
  ): Promise<void> {
    const panel = panelForRun(runId, facet)
    if (!panel || signal.aborted) return

    panel.streaming = true
    panel.text = ''
    panel.error = null

    try {
      const response = await authFetch('/thinking_mode/mindmap/explain_node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
      })

      if (activeRunId.value !== runId || signal.aborted) return

      if (!response.ok) {
        const errBody = (await response.json().catch(() => ({}))) as {
          detail?: unknown
          error_type?: string
        }
        const message = formatHttpErrorDetail(
          errBody.detail,
          t('canvas.mindMapNodeExplain.requestFailed')
        )
        onCrossCuttingError(
          message,
          typeof errBody.error_type === 'string' ? errBody.error_type : undefined
        )
        throw new Error(message)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        const message = t('canvas.mindMapNodeExplain.requestFailed')
        onCrossCuttingError(message)
        throw new Error(message)
      }

      await consumeSseDataLines(
        reader,
        (eventPayload) => {
          if (activeRunId.value !== runId || signal.aborted) {
            return false
          }
          const livePanel = panelForRun(runId, facet)
          if (!livePanel) return false

          const event = eventPayload.event as string | undefined
          if (event === 'token' && typeof eventPayload.text === 'string') {
            livePanel.text += eventPayload.text
            return
          }
          if (event === 'error' && typeof eventPayload.message === 'string') {
            livePanel.error = eventPayload.message
            const errorType =
              typeof eventPayload.error_type === 'string' ? eventPayload.error_type : undefined
            onCrossCuttingError(eventPayload.message, errorType)
            return false
          }
          if (event === 'end') {
            return false
          }
        },
        signal
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      if (activeRunId.value !== runId || signal.aborted) {
        return
      }
      const livePanel = panelForRun(runId, facet)
      if (!livePanel) return
      if (!livePanel.error) {
        livePanel.error =
          err instanceof Error ? err.message : t('canvas.mindMapNodeExplain.requestFailed')
      }
    } finally {
      if (activeRunId.value !== runId) return
      const livePanel = panelForRun(runId, facet)
      if (!livePanel) return
      livePanel.streaming = false
      if (!livePanel.text && livePanel.error) {
        livePanel.text = livePanel.error
      }
    }
  }

  async function startExplain(): Promise<void> {
    const current = target.value
    if (!current) return

    abortController.value?.abort()
    const controller = new AbortController()
    abortController.value = controller
    const runId = activeRunId.value + 1
    activeRunId.value = runId

    const explainSessionId = safeRandomUUID()

    loading.value = true
    panels.value = emptyPanels()

    let toastedError = false
    const onCrossCuttingError = (message: string, errorType?: string): void => {
      if (toastedError || activeRunId.value !== runId) return
      toastedError = true
      notifyRunError(runId, message, errorType)
    }

    const payloads = EXPLAIN_FACETS.map((facet) => ({
      facet,
      payload: buildExplainPayload(current.nodeId, current.nodeLabel, facet, explainSessionId),
    }))

    try {
      await Promise.all(
        payloads.map(({ facet, payload }) =>
          streamFacet(runId, facet, payload, controller.signal, onCrossCuttingError)
        )
      )

      if (activeRunId.value !== runId || controller.signal.aborted || !visible.value) {
        return
      }

      const failed = panels.value.filter((panel) => panel.error)
      const succeeded = panels.value.filter((panel) => !panel.error && panel.text.trim())
      if (failed.length === 0 && succeeded.length === EXPLAIN_FACETS.length) {
        notify.success(t('canvas.mindMapNodeExplain.toastSuccess'))
      } else if (failed.length > 0 && succeeded.length > 0 && !toastedError) {
        notify.warning(t('canvas.mindMapNodeExplain.toastPartial'))
      } else if (failed.length === EXPLAIN_FACETS.length && !toastedError) {
        notify.error(t('canvas.mindMapNodeExplain.requestFailed'))
      }
    } finally {
      if (activeRunId.value === runId && abortController.value === controller) {
        loading.value = false
        abortController.value = null
      }
    }
  }

  function openExplain(nodeId: string, nodeLabel?: string): void {
    const label = (nodeLabel ?? resolveNodeLabel(nodeId)).trim()
    if (!label || isPlaceholderText(label)) return

    // Drop any prior node session before starting a new one.
    clearSession()
    target.value = { nodeId, nodeLabel: label }
    visible.value = true
    void startExplain()
  }

  // Closing the dialog (X / mask / Esc) only flips v-model — still tear down streams.
  watch(visible, (isOpen) => {
    if (!isOpen) {
      clearSession()
    }
  })

  // Leave / switch diagram / canvas reset must abort streams and drop modal state.
  watch(
    () => savedDiagramsStore.activeDiagramId,
    (nextId, prevId) => {
      if (nextId === prevId) return
      close()
    }
  )

  const stopResetListener = eventBus.on('diagram:reset_requested', () => {
    close()
  })

  onUnmounted(() => {
    stopResetListener()
    close()
  })

  return {
    visible,
    target,
    panels,
    loading,
    openExplain,
    close,
  }
}
