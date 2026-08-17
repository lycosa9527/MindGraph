/**
 * Stream a short everyday gloss for one mind-map node.
 */
import { onUnmounted, ref, watch } from 'vue'

import { useLanguage } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { withMindMapAudienceContext } from '@/composables/mindMap/audience/withMindMapAudienceContext'
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

function normalizeDiagramType(type: DiagramType | null): string {
  if (!type) return 'mindmap'
  return type === 'mind_map' ? 'mindmap' : type
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
  const text = ref('')
  const error = ref<string | null>(null)
  const loading = ref(false)
  const abortController = ref<AbortController | null>(null)
  /** Monotonic run id — ignore late writes from aborted generations. */
  const activeRunId = ref(0)

  function resolveNodeLabel(nodeId: string): string {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    return (node?.text ?? '').trim()
  }

  function buildExplainPayload(nodeId: string, nodeLabel: string, explainSessionId: string) {
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    const ctx = collectMindMapExplainContext(nodes, connections, nodeId)
    const topicNode = nodes.find((n) => n.id === 'topic')
    const fallbackTopic = (topicNode?.text ?? diagramStore.effectiveTitle ?? '').trim()

    return withMindMapAudienceContext(
      {
        session_id: explainSessionId,
        node_id: nodeId,
        node_label: nodeLabel,
        topic: ctx?.topic || fallbackTopic,
        diagram_type: normalizeDiagramType(diagramStore.type),
        facet: 'meaning' satisfies MindMapExplainFacet,
        top_level_branches: ctx?.topLevelBranches ?? [],
        ancestor_path: ctx?.ancestorPath ?? [],
        sibling_branches: ctx?.siblingBranches ?? [],
        child_branches: ctx?.childBranches ?? [],
        language: promptLanguage.value,
        diagram_id: savedDiagramsStore.activeDiagramId ?? undefined,
      },
      promptLanguage.value
    )
  }

  function clearSession(): void {
    abortController.value?.abort()
    abortController.value = null
    activeRunId.value += 1
    target.value = null
    text.value = ''
    error.value = null
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

  async function streamExplain(
    runId: number,
    payload: Record<string, unknown>,
    signal: AbortSignal
  ): Promise<void> {
    if (signal.aborted) return

    loading.value = true
    text.value = ''
    error.value = null

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
        notifyRunError(
          runId,
          message,
          typeof errBody.error_type === 'string' ? errBody.error_type : undefined
        )
        error.value = message
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        const message = t('canvas.mindMapNodeExplain.requestFailed')
        notifyRunError(runId, message)
        error.value = message
        return
      }

      await consumeSseDataLines(
        reader,
        (eventPayload) => {
          if (activeRunId.value !== runId || signal.aborted) {
            return false
          }

          const event = eventPayload.event as string | undefined
          if (event === 'token' && typeof eventPayload.text === 'string') {
            text.value += eventPayload.text
            return
          }
          if (event === 'error' && typeof eventPayload.message === 'string') {
            error.value = eventPayload.message
            const errorType =
              typeof eventPayload.error_type === 'string' ? eventPayload.error_type : undefined
            notifyRunError(runId, eventPayload.message, errorType)
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
      if (!error.value) {
        error.value =
          err instanceof Error ? err.message : t('canvas.mindMapNodeExplain.requestFailed')
        notifyRunError(runId, error.value)
      }
    } finally {
      if (activeRunId.value === runId) {
        loading.value = false
        if (!text.value && error.value) {
          text.value = error.value
        }
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

    const payload = buildExplainPayload(current.nodeId, current.nodeLabel, safeRandomUUID())

    try {
      await streamExplain(runId, payload, controller.signal)
    } finally {
      if (activeRunId.value === runId && abortController.value === controller) {
        abortController.value = null
      }
    }
  }

  function openExplain(nodeId: string, nodeLabel?: string): void {
    const label = (nodeLabel ?? resolveNodeLabel(nodeId)).trim()
    if (!label || isPlaceholderText(label)) return

    clearSession()
    target.value = { nodeId, nodeLabel: label }
    visible.value = true
    void startExplain()
  }

  watch(visible, (isOpen) => {
    if (!isOpen) {
      clearSession()
    }
  })

  watch(
    () => savedDiagramsStore.activeDiagramId,
    (nextId, prevId) => {
      if (nextId === prevId) return
      close()
    }
  )

  watch(
    () => diagramStore.data?.nodes,
    (nodes) => {
      const nodeId = target.value?.nodeId
      if (!visible.value || !nodeId) return
      if (!nodes?.some((node) => node.id === nodeId)) {
        close()
      }
    }
  )

  const stopResetListener = eventBus.on('diagram:reset_requested', () => {
    close()
  })

  const stopPaneClickListener = eventBus.on('canvas:pane_clicked', () => {
    close()
  })

  onUnmounted(() => {
    stopResetListener()
    stopPaneClickListener()
    close()
  })

  return {
    visible,
    target,
    text,
    error,
    loading,
    openExplain,
    close,
  }
}
