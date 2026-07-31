/**
 * Maite demo mode — mentor chat with decompose and follow-up streaming.
 */
import { computed, ref } from 'vue'

import { useMaiteMentorStream } from '@/composables/maite/useMaiteMentorStream'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteChatMessage, MaiteDecomposeTables } from '@/types/maite'

function createMessage(role: MaiteChatMessage['role'], content: string): MaiteChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    createdAt: Date.now(),
  }
}

function normalizeTableRows(rows: unknown[]): Record<string, string>[] {
  return rows.map((row, index) => {
    if (typeof row === 'string') {
      return { content: row, index: String(index + 1) }
    }
    if (row && typeof row === 'object') {
      const record = row as Record<string, unknown>
      const normalized: Record<string, string> = {}
      for (const [key, value] of Object.entries(record)) {
        normalized[key] = value == null ? '' : String(value)
      }
      return normalized
    }
    return { content: String(row), index: String(index + 1) }
  })
}

function normalizeDecompose(payload: unknown): MaiteDecomposeTables {
  const data = (payload ?? {}) as Record<string, unknown>
  return {
    condition_table: normalizeTableRows(Array.isArray(data.condition_table) ? data.condition_table : []),
    step_table: normalizeTableRows(Array.isArray(data.step_table) ? data.step_table : []),
    model_table: normalizeTableRows(Array.isArray(data.model_table) ? data.model_table : []),
    next_question: typeof data.next_question === 'string' ? data.next_question : '',
    opening_guidance: typeof data.opening_guidance === 'string' ? data.opening_guidance : '',
  }
}

export function useMaiteDemo() {
  const store = useMaiteStore()
  const mentorStream = useMaiteMentorStream('MaiteDemo')

  const messages = ref<MaiteChatMessage[]>([])
  const decomposition = ref<MaiteDecomposeTables | null>(null)
  const replyDraft = ref('')
  const errorMessage = ref('')

  const canDecompose = computed(
    () => store.currentProblemText.trim().length > 0 && !mentorStream.isStreaming.value
  )

  const canFollowUp = computed(
    () =>
      replyDraft.value.trim().length > 0 &&
      decomposition.value !== null &&
      !mentorStream.isStreaming.value
  )

  function resetDemo(): void {
    messages.value = []
    decomposition.value = null
    replyDraft.value = ''
    errorMessage.value = ''
    mentorStream.stopStream()
  }

  async function runDecompose(): Promise<void> {
    const question = store.currentProblemText.trim()
    if (!question) {
      return
    }

    errorMessage.value = ''
    messages.value = [createMessage('user', question)]

    const result = await mentorStream.runDecomposeStream(question)
    if (!result) {
      errorMessage.value = 'decompose_failed'
      return
    }

    const tables = normalizeDecompose(result)
    decomposition.value = tables

    const assistantText = [
      tables.opening_guidance,
      tables.next_question ? `引导问题：${tables.next_question}` : '',
    ]
      .filter(Boolean)
      .join('\n\n')

    messages.value.push(createMessage('assistant', assistantText || '分解完成，请查看下方三表。'))
  }

  async function runFollowUp(): Promise<void> {
    const question = store.currentProblemText.trim()
    const reply = replyDraft.value.trim()
    if (!question || !reply || !decomposition.value) {
      return
    }

    errorMessage.value = ''
    messages.value.push(createMessage('user', reply))
    replyDraft.value = ''

    const history = messages.value.map((message) => ({
      role: message.role,
      content: message.content,
    }))

    const result = await mentorStream.runFollowUpStream({
      question,
      reply,
      history,
      decomposition: decomposition.value,
    })

    if (!result) {
      errorMessage.value = 'follow_up_failed'
      return
    }

    const assistantText = [result.reply, result.guiding_question ? `追问：${result.guiding_question}` : '']
      .filter(Boolean)
      .join('\n\n')

    messages.value.push(createMessage('assistant', assistantText))
  }

  function stopStreaming(): void {
    mentorStream.stopStream()
    eventBus.emit('maite:mentor_stream_stop', {})
  }

  return {
    messages,
    decomposition,
    replyDraft,
    errorMessage,
    canDecompose,
    canFollowUp,
    isStreaming: mentorStream.isStreaming,
    streamStatus: mentorStream.streamStatus,
    streamPreview: mentorStream.streamPreview,
    runDecompose,
    runFollowUp,
    stopStreaming,
    resetDemo,
  }
}
