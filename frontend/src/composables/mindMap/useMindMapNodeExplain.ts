/**
 * Stream Kitty's educational reflection on a mind map node (cognitive conflict / inquiry).
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables'
import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'
import { useDiagramStore, useSavedDiagramsStore } from '@/stores'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'
import { collectMindMapExplainContext } from '@/utils/mindMapExplainContext'
import { consumeSseDataLines } from '@/utils/mindMateSseStream'

export type MindMapNodeExplainTarget = {
  nodeId: string
  nodeLabel: string
}

export type MindMapNodeExplainMessage = {
  id: string
  role: 'user' | 'kitty'
  text: string
  streaming?: boolean
}

type ExplainHistoryTurn = {
  role: 'user' | 'assistant'
  content: string
}

let messageSeq = 0

function nextMessageId(): string {
  messageSeq += 1
  return `node-explain-${messageSeq}`
}

function normalizeDiagramType(type: DiagramType | null): string {
  if (!type) return 'mindmap'
  return type === 'mind_map' ? 'mindmap' : type
}

export function useMindMapNodeExplain() {
  const { promptLanguage, t } = useLanguage()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  const visible = ref(false)
  const target = ref<MindMapNodeExplainTarget | null>(null)
  const messages = ref<MindMapNodeExplainMessage[]>([])
  const draft = ref('')
  const loading = ref(false)
  const errorMessage = ref<string | null>(null)
  const abortController = ref<AbortController | null>(null)

  const kittyAgentState = computed((): KittyAgentState => {
    if (errorMessage.value) return 'error'
    const streaming = messages.value.find((msg) => msg.streaming)
    if (loading.value && (!streaming || !streaming.text)) return 'connecting'
    if (loading.value) return 'speaking'
    return 'idle'
  })

  function resolveNodeLabel(nodeId: string): string {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    return (node?.text ?? '').trim()
  }

  function buildExplainPayload(
    nodeId: string,
    nodeLabel: string,
    options?: { history?: ExplainHistoryTurn[]; userMessage?: string }
  ) {
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    const ctx = collectMindMapExplainContext(nodes, connections, nodeId)
    const topicNode = nodes.find((n) => n.id === 'topic')
    const fallbackTopic = (topicNode?.text ?? diagramStore.effectiveTitle ?? '').trim()

    return {
      node_id: nodeId,
      node_label: nodeLabel,
      topic: ctx?.topic || fallbackTopic,
      diagram_type: normalizeDiagramType(diagramStore.type),
      top_level_branches: ctx?.topLevelBranches ?? [],
      ancestor_path: ctx?.ancestorPath ?? [],
      sibling_branches: ctx?.siblingBranches ?? [],
      child_branches: ctx?.childBranches ?? [],
      language: promptLanguage.value,
      diagram_id: savedDiagramsStore.activeDiagramId ?? undefined,
      history: options?.history,
      user_message: options?.userMessage,
    }
  }

  function pushMessage(role: MindMapNodeExplainMessage['role'], text: string, streaming = false): string {
    const id = nextMessageId()
    messages.value.push({ id, role, text, streaming })
    return id
  }

  function appendToMessage(messageId: string, chunk: string): void {
    const message = messages.value.find((item) => item.id === messageId)
    if (message) {
      message.text += chunk
    }
  }

  function finalizeMessage(messageId: string): void {
    const message = messages.value.find((item) => item.id === messageId)
    if (message) {
      message.streaming = false
    }
  }

  function buildHistoryBeforeLastUser(): ExplainHistoryTurn[] {
    const completed = messages.value.filter((msg) => !msg.streaming)
    if (completed.length < 2) return []
    const prior = completed.slice(0, -1)
    return prior.map((msg) => ({
      role: msg.role === 'kitty' ? 'assistant' : 'user',
      content: msg.text,
    }))
  }

  function close(): void {
    abortController.value?.abort()
    abortController.value = null
    visible.value = false
    target.value = null
    messages.value = []
    draft.value = ''
    loading.value = false
    errorMessage.value = null
  }

  function openExplain(nodeId: string, nodeLabel?: string): void {
    const label = (nodeLabel ?? resolveNodeLabel(nodeId)).trim()
    if (!label) return

    abortController.value?.abort()
    abortController.value = null
    target.value = { nodeId, nodeLabel: label }
    messages.value = []
    draft.value = ''
    errorMessage.value = null
    visible.value = true

    const initialPrompt = t('canvas.mindMapNodeExplain.userPrompt', { node: label })
    pushMessage('user', initialPrompt)
    void startExplain()
  }

  async function startExplain(followUpText?: string): Promise<void> {
    const current = target.value
    if (!current) return

    abortController.value?.abort()
    const controller = new AbortController()
    abortController.value = controller

    loading.value = true
    errorMessage.value = null

    const kittyMessageId = pushMessage('kitty', '', true)

    const trimmedFollowUp = followUpText?.trim()
    const payload = buildExplainPayload(current.nodeId, current.nodeLabel, {
      history: trimmedFollowUp ? buildHistoryBeforeLastUser() : undefined,
      userMessage: trimmedFollowUp,
    })

    try {
      const response = await authFetch('/thinking_mode/mindmap/explain_node', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errBody = (await response.json().catch(() => ({}))) as { detail?: string }
        throw new Error(
          typeof errBody.detail === 'string'
            ? errBody.detail
            : t('canvas.mindMapNodeExplain.requestFailed')
        )
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error(t('canvas.mindMapNodeExplain.requestFailed'))
      }

      await consumeSseDataLines(
        reader,
        (payload) => {
          const event = payload.event as string | undefined
          if (event === 'token' && typeof payload.text === 'string') {
            appendToMessage(kittyMessageId, payload.text)
            return
          }
          if (event === 'error' && typeof payload.message === 'string') {
            errorMessage.value = payload.message
            return false
          }
          if (event === 'end') {
            return false
          }
        },
        controller.signal
      )
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const msg = err instanceof Error ? err.message : t('canvas.mindMapNodeExplain.requestFailed')
      errorMessage.value = msg
    } finally {
      finalizeMessage(kittyMessageId)
      const kittyMessage = messages.value.find((item) => item.id === kittyMessageId)
      if (kittyMessage && !kittyMessage.text && errorMessage.value) {
        kittyMessage.text = errorMessage.value
      }
      if (abortController.value === controller) {
        loading.value = false
        abortController.value = null
      }
    }
  }

  function sendDraft(): void {
    const text = draft.value.trim()
    if (!text || loading.value) return
    draft.value = ''
    pushMessage('user', text)
    void startExplain(text)
  }

  return {
    visible,
    target,
    messages,
    draft,
    loading,
    errorMessage,
    kittyAgentState,
    openExplain,
    close,
    sendDraft,
  }
}
