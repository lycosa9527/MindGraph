/**
 * Maite demo mode — mentor chat with decompose and follow-up streaming.
 */
import { computed, onScopeDispose, ref, watch } from 'vue'

import { getSnapshot, submitDecompose } from '@/api/maite/inquiry'
import { decompose as decomposeRequest, followUp as followUpRequest } from '@/api/maite/mentor'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteMentorStream } from '@/composables/maite/useMaiteMentorStream'
import { persistMaitePractice } from '@/composables/maite/useMaitePracticePersist'
import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteChatMessage, MaiteDecomposeTables, MaiteMode } from '@/types/maite'

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
  const { t } = useLanguage()
  const mentorStream = useMaiteMentorStream('MaiteDemo')

  const messages = ref<MaiteChatMessage[]>([])
  const decomposition = ref<MaiteDecomposeTables | null>(null)
  const replyDraft = ref('')
  const errorMessage = ref('')
  const fallbackBusy = ref(false)
  const practiceSessionId = ref<number | null>(null)
  const liveAssistantId = ref<string | null>(null)

  const isBusy = computed(() => mentorStream.isStreaming.value || fallbackBusy.value)

  const canDecompose = computed(
    () => store.currentProblemText.trim().length > 0 && !isBusy.value
  )

  const canFollowUp = computed(
    () =>
      replyDraft.value.trim().length > 0 &&
      decomposition.value !== null &&
      !isBusy.value
  )

  watch(
    () => mentorStream.streamPreview.value,
    (preview) => {
      if (!liveAssistantId.value || !preview) {
        return
      }
      const message = messages.value.find((item) => item.id === liveAssistantId.value)
      if (message) {
        message.content = preview
      }
    }
  )

  function resetDemo(): void {
    messages.value = []
    decomposition.value = null
    replyDraft.value = ''
    errorMessage.value = ''
    fallbackBusy.value = false
    practiceSessionId.value = null
    liveAssistantId.value = null
    mentorStream.stopStream()
  }

  async function ensurePracticeSession(
    question: string,
    imageUrl?: string
  ): Promise<number | null> {
    // Prefer session already created at OCR upload time.
    if (practiceSessionId.value) {
      return practiceSessionId.value
    }
    if (store.activeSessionId) {
      practiceSessionId.value = store.activeSessionId
      return practiceSessionId.value
    }
    try {
      const session = await persistMaitePractice({
        text: question,
        imageUrl,
        mode: 'demo',
      })
      if (!session) {
        return null
      }
      practiceSessionId.value = session.id
      notify.success(t('maite.toast.practice_saved'))
      return session.id
    } catch (error: unknown) {
      eventBus.emit('maite:error', {
        message: error instanceof Error ? error.message : 'create_failed',
        source: 'demo_practice_persist',
      })
      return null
    }
  }

  async function persistDecomposeTables(tables: MaiteDecomposeTables): Promise<void> {
    const sessionId = practiceSessionId.value
    if (!sessionId) {
      return
    }
    try {
      await submitDecompose(sessionId, {
        condition_table: tables.condition_table,
        step_table: tables.step_table,
        model_table: tables.model_table,
      })
      eventBus.emit('maite:practice_invalidate', { reason: 'demo_decompose_saved' })
    } catch (error: unknown) {
      eventBus.emit('maite:error', {
        message: error instanceof Error ? error.message : 'submit_failed',
        source: 'demo_decompose_persist',
      })
    }
  }

  function upsertLiveAssistant(content: string): string {
    if (liveAssistantId.value) {
      const existing = messages.value.find((item) => item.id === liveAssistantId.value)
      if (existing) {
        existing.content = content
        return existing.id
      }
    }
    const message = createMessage('assistant', content)
    liveAssistantId.value = message.id
    messages.value.push(message)
    return message.id
  }

  async function runDecompose(
    problemText?: string,
    options: { force?: boolean; imageUrl?: string } = {}
  ): Promise<void> {
    // Template @click passes a MouseEvent; only honor real string overrides (OCR).
    const override = typeof problemText === 'string' ? problemText : undefined
    const question = (override ?? store.currentProblemText).trim()
    if (!question) {
      return
    }
    if (isBusy.value && !options.force) {
      return
    }
    if (options.force && isBusy.value) {
      stopStreaming()
      fallbackBusy.value = false
    }

    store.setCurrentProblemText(question)
    errorMessage.value = ''
    liveAssistantId.value = null
    // Re-run after tables exist → new conversation; OCR path reuses uploaded session.
    if (decomposition.value) {
      practiceSessionId.value = null
      store.setActiveSessionId(null)
    }
    decomposition.value = null
    messages.value = [createMessage('user', question)]
    upsertLiveAssistant(t('maite.stream.working'))

    notify.info(t('maite.toast.decompose_started'))
    await ensurePracticeSession(question, options.imageUrl)

    let result = await mentorStream.runDecomposeStream(question)
    if (!result) {
      // Stream hung/empty: fall back to non-streaming decompose.
      notify.warning(t('maite.toast.decompose_fallback'))
      fallbackBusy.value = true
      upsertLiveAssistant(t('maite.stream.working'))
      try {
        result = await decomposeRequest({ question })
      } catch (error: unknown) {
        errorMessage.value = 'decompose_failed'
        eventBus.emit('maite:error', {
          message: error instanceof Error ? error.message : 'decompose_failed',
          source: 'demo_decompose_fallback',
        })
        return
      } finally {
        fallbackBusy.value = false
      }
    }

    const tables = normalizeDecompose(result)
    decomposition.value = tables
    void persistDecomposeTables(tables)

    const assistantText = [
      tables.opening_guidance,
      tables.next_question
        ? `${t('maite.demo.guidingQuestionPrefix')}${tables.next_question}`
        : '',
    ]
      .filter(Boolean)
      .join('\n\n')

    upsertLiveAssistant(assistantText || t('maite.demo.decomposeComplete'))
    liveAssistantId.value = null
    notify.success(t('maite.toast.decompose_complete'))
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
    liveAssistantId.value = null
    upsertLiveAssistant(t('maite.stream.working'))

    const history = messages.value
      .filter((message) => message.id !== liveAssistantId.value)
      .map((message) => ({
        role: message.role,
        content: message.content,
      }))

    let result = await mentorStream.runFollowUpStream({
      question,
      reply,
      history,
      decomposition: decomposition.value,
    })

    if (!result) {
      notify.warning(t('maite.toast.decompose_fallback'))
      fallbackBusy.value = true
      try {
        result = await followUpRequest({
          question,
          reply,
          history,
          decomposition: decomposition.value,
        })
      } catch (error: unknown) {
        errorMessage.value = 'follow_up_failed'
        eventBus.emit('maite:error', {
          message: error instanceof Error ? error.message : 'follow_up_failed',
          source: 'demo_follow_up_fallback',
        })
        return
      } finally {
        fallbackBusy.value = false
      }
    }

    const assistantText = [
      result.reply,
      result.guiding_question
        ? `${t('maite.demo.followUpPrefix')}${result.guiding_question}`
        : '',
    ]
      .filter(Boolean)
      .join('\n\n')

    upsertLiveAssistant(assistantText)
    liveAssistantId.value = null
  }

  function stopStreaming(): void {
    mentorStream.stopStream()
    eventBus.emit('maite:mentor_stream_stop', {})
  }

  async function openPracticeSession(sessionId: number): Promise<void> {
    try {
      const snapshot = await getSnapshot(sessionId)
      const problem = snapshot.problem as Record<string, unknown> | null | undefined
      const text =
        (typeof problem?.clean_text === 'string' && problem.clean_text) ||
        (typeof problem?.raw_text === 'string' && problem.raw_text) ||
        ''
      store.setCurrentProblemText(text)
      practiceSessionId.value = sessionId
      store.setActiveSessionId(sessionId)
      messages.value = text ? [createMessage('user', text)] : []
      liveAssistantId.value = null
      decomposition.value = null
      if (snapshot.decompose) {
        const tables = normalizeDecompose(snapshot.decompose)
        decomposition.value = tables
        const assistantText = [
          tables.opening_guidance,
          tables.next_question
            ? `${t('maite.demo.guidingQuestionPrefix')}${tables.next_question}`
            : '',
        ]
          .filter(Boolean)
          .join('\n\n')
        if (assistantText) {
          messages.value.push(createMessage('assistant', assistantText))
        }
      }
    } catch (error: unknown) {
      eventBus.emit('maite:error', {
        message: error instanceof Error ? error.message : 'load_failed',
        source: 'demo_session_open',
      })
    }
  }

  // Demo OCR → persist practice + auto 开始分解 with streaming.
  const offOcrCompleted = eventBus.on('maite:ocr_completed', ({ text, scene, imageUrl }) => {
    if (scene !== 'demo') {
      return
    }
    const question = text.trim()
    if (!question) {
      return
    }
    void runDecompose(question, { force: true, imageUrl })
  })

  const offSessionOpened = eventBus.on('maite:session_opened', ({ sessionId, mode }) => {
    if ((mode as MaiteMode) !== 'demo') {
      return
    }
    void openPracticeSession(sessionId)
  })

  onScopeDispose(() => {
    offOcrCompleted()
    offSessionOpened()
  })

  return {
    messages,
    decomposition,
    replyDraft,
    errorMessage,
    canDecompose,
    canFollowUp,
    isStreaming: isBusy,
    streamStatus: mentorStream.streamStatus,
    streamPreview: mentorStream.streamPreview,
    runDecompose,
    runFollowUp,
    stopStreaming,
    resetDemo,
  }
}
