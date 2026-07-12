/**
 * Shared Kitty ASR commit policy — utterance correlation, dedupe, release-only vs final.
 * Emits kitty:edit_turn_requested; does not hub-sync or sendText.
 */
import { onUnmounted, ref, type Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { failKittyTurn, recordPipelineEvent } from '@/composables/kitty/pipeline/trace'
import type { KittyLane, KittyTurnContext } from '@/composables/kitty/pipeline/types'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type KittyAsrCommitMode = 'release_only' | 'final_or_stopped'

export type KittyAsrCommitResult = {
  committed: boolean
  text?: string
  ctx?: KittyTurnContext
  skippedReason?: 'empty' | 'stale' | 'deduped' | 'already_committed'
}

function normalizeAsrCommitKey(text: string): string {
  return text
    .trim()
    .replace(/[。．.！？!?，,、；;：:\s]+$/gu, '')
    .trim()
}

export function useKittyAsrSession(options: {
  mode: KittyAsrCommitMode | Ref<KittyAsrCommitMode>
  lane: KittyLane | Ref<KittyLane>
  getScope: () => string
  draft: Ref<string>
  onCommit?: (text: string, ctx: KittyTurnContext) => void
  ownerId?: string
}): {
  holdTranscript: Ref<string>
  holdHadSpeech: Ref<boolean>
  activeUtteranceId: Ref<string | null>
  commitTranscript: (raw: string, utteranceId?: string) => KittyAsrCommitResult
  resetHold: () => void
  bindBus: () => void
} {
  const ownerId = options.ownerId ?? 'KittyAsrSession'
  const holdTranscript = ref('')
  const holdHadSpeech = ref(false)
  const holdListening = ref(false)
  const activeUtteranceId = ref<string | null>(null)
  const asrFinalCommitted = ref(false)
  let lastAsrCommitText = ''
  let lastAsrCommitAt = 0

  function modeValue(): KittyAsrCommitMode {
    const m = options.mode
    return typeof m === 'object' && m !== null && 'value' in m ? m.value : m
  }

  function laneValue(): KittyLane {
    const l = options.lane
    return typeof l === 'object' && l !== null && 'value' in l ? l.value : l
  }

  function utteranceMatches(utteranceId?: string): boolean {
    if (!utteranceId) {
      return holdListening.value
    }
    if (activeUtteranceId.value == null) {
      activeUtteranceId.value = utteranceId
      return true
    }
    return utteranceId === activeUtteranceId.value
  }

  function resetHold(): void {
    holdTranscript.value = ''
    holdListening.value = false
    holdHadSpeech.value = false
    activeUtteranceId.value = null
  }

  function commitTranscript(raw: string, utteranceId?: string): KittyAsrCommitResult {
    const text = raw.trim()
    const scope = options.getScope().trim()
    const lane = laneValue()
    const requestId = safeRandomUUID()
    const ctx: KittyTurnContext = {
      requestId,
      utteranceId: utteranceId ?? activeUtteranceId.value ?? undefined,
      scope: scope || 'scope',
      lane,
    }

    if (!text) {
      recordPipelineEvent({
        ctx,
        module: 'asr',
        step: 'S05_asr_commit',
        status: 'skip',
        errorCode: 'empty_transcript',
        detail: 'empty transcript',
      })
      return { committed: false, skippedReason: 'empty' }
    }
    if (asrFinalCommitted.value) {
      return { committed: false, skippedReason: 'already_committed' }
    }
    if (utteranceId && activeUtteranceId.value && utteranceId !== activeUtteranceId.value) {
      failKittyTurn({
        ctx,
        module: 'asr',
        step: 'S05_asr_commit',
        errorCode: 'stale_utterance',
        detail: `stale utt=${utteranceId}`,
      })
      return { committed: false, skippedReason: 'stale' }
    }

    const key = normalizeAsrCommitKey(text)
    const now = Date.now()
    if (key.length > 0 && key === lastAsrCommitText && now - lastAsrCommitAt < 2500) {
      recordPipelineEvent({
        ctx,
        module: 'asr',
        step: 'S05_asr_commit',
        status: 'skip',
        errorCode: 'deduped',
        detail: key.slice(0, 40),
      })
      return { committed: false, skippedReason: 'deduped' }
    }
    if (key.length > 0) {
      lastAsrCommitText = key
    }
    lastAsrCommitAt = now
    asrFinalCommitted.value = true
    options.draft.value = text

    recordPipelineEvent({
      ctx,
      module: 'asr',
      step: 'S05_asr_commit',
      status: 'ok',
      detail: text.slice(0, 80),
    })
    eventBus.emit('kitty:edit_turn_requested', { ctx, text, source: 'asr' })
    options.onCommit?.(text, ctx)
    window.setTimeout(() => {
      asrFinalCommitted.value = false
    }, 3000)
    return { committed: true, text, ctx }
  }

  function onAsrPartial(payload: { text: string; utteranceId?: string }): void {
    if (!utteranceMatches(payload.utteranceId)) {
      return
    }
    if (payload.utteranceId) {
      activeUtteranceId.value = payload.utteranceId
    }
    if (payload.text.trim()) {
      asrFinalCommitted.value = false
      holdListening.value = true
      holdHadSpeech.value = true
      holdTranscript.value = payload.text.trim()
      options.draft.value = holdTranscript.value
      recordPipelineEvent({
        ctx: {
          requestId: `asr-partial-${Date.now()}`,
          utteranceId: activeUtteranceId.value ?? undefined,
          scope: options.getScope() || 'scope',
          lane: laneValue(),
        },
        module: 'asr',
        step: 'S04_asr_audio',
        status: 'ok',
        detail: holdTranscript.value.slice(0, 40),
      })
    }
  }

  function onAsrFinal(payload: { text: string; utteranceId?: string }): void {
    if (!utteranceMatches(payload.utteranceId)) {
      return
    }
    if (payload.utteranceId) {
      activeUtteranceId.value = payload.utteranceId
    }
    const text = payload.text.trim()
    if (!text) {
      return
    }
    holdListening.value = true
    holdHadSpeech.value = true
    holdTranscript.value = text
    options.draft.value = text
    asrFinalCommitted.value = false
    if (modeValue() === 'final_or_stopped') {
      commitTranscript(text, payload.utteranceId)
      resetHold()
    }
  }

  function onAsrStopped(payload?: { utteranceId?: string; text?: string }): void {
    if (
      payload?.utteranceId &&
      activeUtteranceId.value &&
      payload.utteranceId !== activeUtteranceId.value
    ) {
      return
    }
    const payloadText = typeof payload?.text === 'string' ? payload.text.trim() : ''
    const text = (payloadText || holdTranscript.value).trim()
    if (modeValue() === 'release_only') {
      if (!holdHadSpeech.value || !text) {
        resetHold()
        return
      }
      commitTranscript(text, payload?.utteranceId)
      resetHold()
      return
    }
    if (text && !asrFinalCommitted.value) {
      commitTranscript(text, payload?.utteranceId)
    }
    resetHold()
  }

  function onAsrStarted(payload: { utteranceId?: string }): void {
    if (payload.utteranceId) {
      activeUtteranceId.value = payload.utteranceId
    }
    holdListening.value = true
    recordPipelineEvent({
      ctx: {
        requestId: `asr-start-${Date.now()}`,
        utteranceId: payload.utteranceId,
        scope: options.getScope() || 'scope',
        lane: laneValue(),
      },
      module: 'asr',
      step: 'S03_asr_start',
      status: 'ok',
      detail: payload.utteranceId ?? 'started',
    })
  }

  function bindBus(): void {
    eventBus.onWithOwner('kitty:asr_partial', onAsrPartial, ownerId)
    eventBus.onWithOwner('kitty:asr_final', onAsrFinal, ownerId)
    eventBus.onWithOwner('kitty:asr_stopped', onAsrStopped, ownerId)
    eventBus.onWithOwner('kitty:asr_started', onAsrStarted, ownerId)
  }

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(ownerId)
  })

  return {
    holdTranscript,
    holdHadSpeech,
    activeUtteranceId,
    commitTranscript,
    resetHold,
    bindBus,
  }
}
