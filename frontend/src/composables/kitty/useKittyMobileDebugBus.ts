/**
 * Dev-facing voice event log for Mobile Kitty (curated — no streaming SSE chunks).
 */
import { onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { formatKittyActionDebug, normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'

export function useKittyMobileDebugBus(options: {
  ownerId: string
  pushLine: (prefix: string, detail: string) => void
  scheduleContextSync: () => void
}): void {
  const { ownerId, pushLine, scheduleContextSync } = options

  function trace(prefix: string, detail: string, stage?: string): void {
    pushLine(prefix, detail)
    traceKittyWorkflow('mobile', stage ?? prefix, detail)
  }

  let assistantChunkBuffer = ''
  let assistantTextDoneSeen = false

  function resetAssistantTurn(): void {
    assistantChunkBuffer = ''
    assistantTextDoneSeen = false
  }

  eventBus.onWithOwner(
    'voice:started',
    (payload) => {
      resetAssistantTurn()
      const sid = payload.sessionId ?? ''
      pushLine('ws', sid.length > 14 ? `${sid.slice(0, 14)}…` : sid)
      traceKittyWorkflow('mobile', 'ws', 'voice started')
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:stopped',
    () => {
      resetAssistantTurn()
      pushLine('ws', 'voice stopped')
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:connected',
    (payload) => {
      const sid = payload.sessionId ?? ''
      pushLine('ok', sid.length > 14 ? `${sid.slice(0, 14)}…` : sid)
      scheduleContextSync()
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:ws_closed',
    (p) => {
      resetAssistantTurn()
      pushLine('close', `code=${String(p.code ?? '?')}`)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:ws_error',
    (p) => {
      pushLine('err_ws', normalizeKittyDebugText(p.error, 120))
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:server_error',
    (p) => {
      pushLine('err_srv', normalizeKittyDebugText(p.error, 120))
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:transcription',
    (p) => {
      const text = normalizeKittyDebugText(p.text, 240)
      if (text !== '') {
        pushLine('user', text)
      }
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:assistant_text_done',
    (p) => {
      assistantTextDoneSeen = true
      const text = normalizeKittyDebugText(p.text, 240)
      if (text !== '') {
        pushLine('assistant', text)
      }
      assistantChunkBuffer = ''
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:text_chunk',
    (p) => {
      if (assistantTextDoneSeen) {
        return
      }
      assistantChunkBuffer += String(p.text ?? '')
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:response_done',
    () => {
      if (assistantTextDoneSeen) {
        resetAssistantTurn()
        return
      }
      const text = normalizeKittyDebugText(assistantChunkBuffer, 240)
      if (text !== '') {
        pushLine('assistant', text)
      }
      resetAssistantTurn()
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:action_executed',
    (p) => {
      const params =
        p.params != null && typeof p.params === 'object'
          ? (p.params as Record<string, unknown>)
          : {}
      const extra = formatKittyActionDebug(p.action, params)
      trace(`act:${p.action}`, extra, 'action')
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:diagram_update_executed',
    (p) => {
      const detail =
        typeof p.summary === 'string' && p.summary.trim() !== ''
          ? p.summary
          : p.action
      pushLine('diagram', detail)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'kitty:diagram_review_annotation',
    (p) => {
      const summary = normalizeKittyDebugText(p.summary, 160)
      const count = Array.isArray(p.items) ? p.items.length : 0
      const detail =
        summary !== '' ? `${summary} (${count} nodes)` : `review ${count} node${count === 1 ? '' : 's'}`
      pushLine('review', detail)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'voice:context_mutation_ack',
    (p) => {
      const ok = p.ok !== false
      const rev = typeof p.revision === 'number' ? ` rev=${p.revision}` : ''
      const persist = p.persist_library === true ? ' persist' : ''
      const err =
        typeof p.library_snapshot_error === 'string' ? p.library_snapshot_error : p.error
      const detail = ok
        ? `hub ack ok${rev}${persist}`
        : `hub ack failed ${normalizeKittyDebugText(String(err ?? 'rejected'), 80)}`
      pushLine('#hub', detail)
    },
    ownerId
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(ownerId)
  })
}
