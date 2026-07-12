import type { Ref, ShallowRef } from 'vue'

import { type EventTypes, eventBus } from '@/composables/core/useEventBus'
import { applyKittyRemoteLlmModel } from '@/composables/kitty/applyKittyRemoteLlmModel'
import { executeKittyAgentAction } from '@/composables/kitty/kittyAgentActions'
import { arrayBufferToBase64, base64ToArrayBuffer } from '@/composables/kitty/kittyAgentAudioCodec'
import { normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'
import type { KittyAgentState } from '@/composables/kitty/kittyAgentTypes'
import { applyKittyRemoteCanvasSelection } from '@/composables/kitty/kittySelectionApply'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useKittySessionStore } from '@/stores/kittySession'
import type { DiagramEditExpectedEffect } from '@/utils/diagramEditVerify'

export interface KittyInboundHandlerDeps {
  destroyed: () => boolean
  cleaningUp: () => boolean
  textOnly?: boolean
  /** Mobile lane is mic+chat only — never owns canvas mutation apply. */
  clientLane?: 'mobile' | 'desktop'
  isVoiceActive: Ref<boolean>
  state: Ref<KittyAgentState>
  sessionId: Ref<string | null>
  lastTranscription: Ref<string | null>
  lastError: Ref<string | null>
  onTranscription?: (text: string) => void
  onTextChunk?: (text: string) => void
  onError?: (error: string) => void
  sendDiagramMutationAck?: (payload: Record<string, unknown>) => void
  hubScopeRevision?: number | null
  diagramSessionId?: string | null
  buildDiagramContext?: () => import('@/composables/kitty/kittyAgentTypes').KittyAgentContext
  updateContext?: (
    context: import('@/composables/kitty/kittyAgentTypes').KittyAgentContext,
    options?: import('@/composables/kitty/kittyAgentTypes').KittyContextUpdateOptions
  ) => void
  playAudioChunk: (audioBase64: string, sampleRateHz?: number) => Promise<void>
  stopAudioPlayback: () => void
}

/** Dispatch verified diagram_update: canvas owners apply; thin mobile shows chat only. */
export function dispatchKittyDiagramUpdateInbound(
  data: Record<string, unknown>,
  deps: Pick<
    KittyInboundHandlerDeps,
    | 'clientLane'
    | 'sendDiagramMutationAck'
    | 'buildDiagramContext'
    | 'updateContext'
    | 'diagramSessionId'
  >
): void {
  const diagramAction = String(data.action ?? '')
  const diagramUpdates = (data.updates as Record<string, unknown>) ?? {}
  const mutationId =
    typeof data.mutation_id === 'string' && data.mutation_id.trim() !== ''
      ? data.mutation_id.trim()
      : ''
  const userSummary =
    typeof data.user_summary === 'string' && data.user_summary.trim() !== ''
      ? data.user_summary.trim()
      : ''
  const expectedEffect = data.expected_effect as DiagramEditExpectedEffect | undefined
  const beforeRaw = data.before_fingerprint as
    | { nodes?: unknown[]; connections?: unknown[] }
    | undefined
  const beforeFingerprint =
    beforeRaw && Array.isArray(beforeRaw.nodes) && Array.isArray(beforeRaw.connections)
      ? {
          nodes: beforeRaw.nodes as import('@/types').DiagramNode[],
          connections: beforeRaw.connections as import('@/types').Connection[],
        }
      : undefined

  // Thin mobile: chat summary only — desktop canvas_owner applies + acks.
  if (deps.clientLane === 'mobile') {
    if (userSummary !== '') {
      eventBus.emit('kitty:one_sentence_reply', {
        text: userSummary,
        kind: 'final',
        action: diagramAction || undefined,
      })
    }
    return
  }

  eventBus.emit('kitty:diagram_mutation_requested', {
    action: diagramAction,
    updates: diagramUpdates,
    mutationId: mutationId !== '' ? mutationId : undefined,
    userSummary: userSummary !== '' ? userSummary : undefined,
    expectedEffect,
    beforeFingerprint,
    sendAck: deps.sendDiagramMutationAck,
    hubPersist:
      deps.buildDiagramContext && deps.updateContext
        ? {
            buildContext: deps.buildDiagramContext,
            updateContext: deps.updateContext,
            scope: deps.diagramSessionId ?? null,
          }
        : undefined,
    lane: deps.clientLane === 'desktop' ? 'desktop' : 'mobile',
  })
}

export function handleKittyServerMessage(
  data: Record<string, unknown>,
  deps: KittyInboundHandlerDeps
): void {
  if (deps.destroyed() || deps.cleaningUp()) return

  switch (data.type) {
    case 'connected':
      deps.sessionId.value = String(data.session_id ?? '')
      deps.state.value = 'active'
      eventBus.emit('voice:connected', { sessionId: String(data.session_id ?? '') })
      break

    case 'llm_model_update': {
      void applyKittyRemoteLlmModel(data.selected_llm_model)
      break
    }

    case 'selection_update': {
      const raw = data.selected_nodes
      const selectedNodes = Array.isArray(raw)
        ? raw.filter((item): item is string => typeof item === 'string')
        : []
      applyKittyRemoteCanvasSelection(selectedNodes, { canvasHighlight: false })
      break
    }

    case 'transcription':
      deps.lastTranscription.value = String(data.text ?? '')
      eventBus.emit('voice:transcription', { text: String(data.text ?? '') })
      traceKittyWorkflow('mobile', 'transcription', String(data.text ?? ''))
      deps.onTranscription?.(String(data.text ?? ''))
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'text_chunk':
      if (deps.isVoiceActive.value) break
      {
        const text = String(data.text ?? '')
        const replyKindRaw = data.reply_kind
        const kind =
          replyKindRaw === 'progress'
            ? 'progress'
            : replyKindRaw === 'final'
              ? 'final'
              : 'conversational'
        const actionRaw = data.action
        const clarifyQuestion =
          typeof data.clarify_question === 'string' ? data.clarify_question.trim() : ''
        const clarifyRaw = data.clarify_options
        const choices: Array<{ index: number; label: string }> = []
        if (Array.isArray(clarifyRaw)) {
          for (const item of clarifyRaw) {
            if (typeof item !== 'string' || !item.trim()) {
              continue
            }
            choices.push({ index: choices.length + 1, label: item.trim() })
            if (choices.length >= 3) {
              break
            }
          }
        }
        eventBus.emit('kitty:one_sentence_reply', {
          text: clarifyQuestion || text,
          kind,
          action: typeof actionRaw === 'string' ? actionRaw : undefined,
          choices: choices.length >= 2 ? choices : undefined,
          requestId:
            typeof data.request_id === 'string' && data.request_id.trim()
              ? data.request_id.trim()
              : undefined,
        })
        eventBus.emit('voice:text_chunk', { text })
      }
      break

    case 'audio_chunk':
      {
        const kittySession = useKittySessionStore()
        if (!kittySession.ttsEnabled) break
        if (!deps.destroyed() && !deps.cleaningUp() && !deps.isVoiceActive.value) {
          const rateRaw = data.sample_rate
          const sampleRateHz =
            typeof rateRaw === 'number' && Number.isFinite(rateRaw) && rateRaw > 0
              ? rateRaw
              : undefined
          void deps.playAudioChunk(String(data.audio ?? ''), sampleRateHz)
          deps.state.value = 'speaking'
        }
      }
      break

    case 'tts_done':
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'tts_interrupted':
      deps.stopAudioPlayback()
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'asr_partial':
      {
        const kittySession = useKittySessionStore()
        const text = String(data.text ?? '')
        const utteranceId =
          typeof data.utterance_id === 'string' && data.utterance_id.trim()
            ? data.utterance_id.trim()
            : undefined
        kittySession.setAsrPartialTranscript(text)
        eventBus.emit('kitty:asr_partial', { text, utteranceId })
      }
      break

    case 'asr_final':
      {
        const kittySession = useKittySessionStore()
        const text = String(data.text ?? '')
        const utteranceId =
          typeof data.utterance_id === 'string' && data.utterance_id.trim()
            ? data.utterance_id.trim()
            : undefined
        kittySession.setAsrPartialTranscript(text)
        eventBus.emit('kitty:asr_final', { text, utteranceId })
      }
      break

    case 'asr_started':
      {
        const utteranceId =
          typeof data.utterance_id === 'string' && data.utterance_id.trim()
            ? data.utterance_id.trim()
            : undefined
        useKittySessionStore().setAsrListening(true)
        eventBus.emit('kitty:asr_started', { utteranceId })
      }
      break

    case 'asr_stopped':
      {
        const utteranceId =
          typeof data.utterance_id === 'string' && data.utterance_id.trim()
            ? data.utterance_id.trim()
            : undefined
        const text =
          typeof data.text === 'string' && data.text.trim() ? data.text.trim() : undefined
        useKittySessionStore().setAsrListening(false)
        eventBus.emit('kitty:asr_stopped', { utteranceId, text })
      }
      break

    case 'speech_started':
      eventBus.emit('voice:speech_started', {
        audioStartMs: typeof data.audio_start_ms === 'number' ? data.audio_start_ms : undefined,
      })
      traceKittyWorkflow('mobile', 'speech', 'user speaking')
      deps.stopAudioPlayback()
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'speech_stopped':
      eventBus.emit('voice:speech_stopped', {
        audioEndMs: typeof data.audio_end_ms === 'number' ? data.audio_end_ms : undefined,
      })
      break

    case 'response_done':
      eventBus.emit('voice:response_done', {})
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'response_text_done': {
      const assistantText = normalizeKittyDebugText(data.text, 2000)
      if (assistantText !== '') {
        eventBus.emit('voice:assistant_text_done', { text: assistantText })
      }
      break
    }

    case 'action':
      traceKittyWorkflow('mobile', 'action', String(data.action ?? ''), {
        action: String(data.action ?? ''),
      })
      executeKittyAgentAction(
        String(data.action ?? ''),
        (data.params as Record<string, unknown>) ?? {}
      )
      break

    case 'diagram_update': {
      dispatchKittyDiagramUpdateInbound(data, deps)
      break
    }

    case 'diagram_review_annotation': {
      const rawItems = data.items
      const rows = Array.isArray(rawItems)
        ? (rawItems as Array<Record<string, unknown>>).map((row) => ({
            node_id: String(row.node_id ?? ''),
            reason: typeof row.reason === 'string' ? row.reason : String(row.reason ?? ''),
            suggestion: typeof row.suggestion === 'string' ? row.suggestion : undefined,
          }))
        : []
      eventBus.emit('kitty:diagram_review_annotation', {
        summary: String(data.summary ?? ''),
        items: rows,
      })
      break
    }

    case 'context_mutation_ack': {
      const ackPayload = {
        ok: data.ok !== false,
        revision: typeof data.revision === 'number' ? data.revision : undefined,
        library_snapshot_saved: data.library_snapshot_saved === true,
        library_snapshot_error:
          typeof data.library_snapshot_error === 'string' ? data.library_snapshot_error : undefined,
        idempotency_key:
          typeof data.idempotency_key === 'string' ? data.idempotency_key : undefined,
        persist_library: data.persist_library === true,
        error: typeof data.error === 'string' ? data.error : undefined,
      }
      eventBus.emit('voice:context_mutation_ack', ackPayload)
      const ackDetail = ackPayload.ok
        ? `ok rev=${ackPayload.revision ?? '?'}${ackPayload.persist_library ? ' persist' : ''}`
        : `failed ${ackPayload.error ?? ackPayload.library_snapshot_error ?? 'rejected'}`
      traceKittyWorkflow('hub', 'context_ack', ackDetail)
      break
    }

    case 'error':
      deps.lastError.value = String(data.error ?? '')
      deps.state.value = 'error'
      eventBus.emit('voice:server_error', { error: String(data.error ?? '') })
      deps.onError?.(String(data.error ?? ''))
      break

    default:
      eventBus.emit(`voice:${data.type}` as keyof EventTypes, data)
  }
}

export interface KittyPlaybackDeps {
  destroyed: () => boolean
  cleaningUp: () => boolean
  /** Default CosyVoice PCM rate when chunk omits sample_rate (22050). */
  sampleRate: number
  audioContext: ShallowRef<AudioContext | null>
  isVoiceActive: Ref<boolean>
  isPlaying: Ref<boolean>
  state: Ref<KittyAgentState>
  currentAudioSource: ShallowRef<AudioBufferSourceNode | null>
  audioQueue: Array<{ buffer: AudioBuffer }>
}

/** CosyVoice realtime PCM default (matches services/kitty/tts/cosyvoice_realtime.py). */
export const KITTY_TTS_PCM_SAMPLE_RATE = 22050

export function createKittyPlayback(deps: KittyPlaybackDeps) {
  let nextPlayTime = 0
  const scheduledSources = new Set<AudioBufferSourceNode>()

  function resolvePlaybackRate(sampleRateHz?: number): number {
    if (typeof sampleRateHz === 'number' && Number.isFinite(sampleRateHz) && sampleRateHz > 0) {
      return sampleRateHz
    }
    return deps.sampleRate > 0 ? deps.sampleRate : KITTY_TTS_PCM_SAMPLE_RATE
  }

  function markIdleIfDone(): void {
    if (scheduledSources.size > 0 || deps.audioQueue.length > 0) {
      return
    }
    deps.isPlaying.value = false
    deps.currentAudioSource.value = null
    deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
  }

  function stopSource(source: AudioBufferSourceNode): void {
    try {
      source.onended = null
      source.stop()
      source.disconnect()
    } catch {
      /* already stopped */
    }
    scheduledSources.delete(source)
  }

  function scheduleQueuedChunks(): void {
    const ctx = deps.audioContext.value
    if (!ctx || deps.destroyed() || ctx.state === 'closed') {
      deps.audioQueue.length = 0
      for (const source of [...scheduledSources]) {
        stopSource(source)
      }
      deps.isPlaying.value = false
      deps.currentAudioSource.value = null
      return
    }
    if (deps.isVoiceActive.value) {
      deps.audioQueue.length = 0
      for (const source of [...scheduledSources]) {
        stopSource(source)
      }
      deps.isPlaying.value = false
      deps.currentAudioSource.value = null
      deps.state.value = 'listening'
      return
    }

    while (deps.audioQueue.length > 0) {
      const chunk = deps.audioQueue.shift()
      if (!chunk) {
        break
      }
      const source = ctx.createBufferSource()
      source.buffer = chunk.buffer
      source.connect(ctx.destination)
      const startAt = Math.max(ctx.currentTime, nextPlayTime)
      nextPlayTime = startAt + chunk.buffer.duration
      deps.isPlaying.value = true
      deps.state.value = 'speaking'
      deps.currentAudioSource.value = source
      scheduledSources.add(source)
      source.onended = () => {
        scheduledSources.delete(source)
        if (deps.currentAudioSource.value === source) {
          deps.currentAudioSource.value = null
        }
        if (deps.destroyed()) {
          deps.isPlaying.value = false
          return
        }
        markIdleIfDone()
      }
      try {
        source.start(startAt)
      } catch (error) {
        console.error('[KittyAgent] Audio schedule error:', error)
        scheduledSources.delete(source)
        markIdleIfDone()
      }
    }
  }

  async function playAudioChunk(audioBase64: string, sampleRateHz?: number): Promise<void> {
    if (!deps.audioContext.value || deps.destroyed() || deps.cleaningUp()) return
    if (deps.isVoiceActive.value) return

    try {
      if (deps.audioContext.value.state === 'suspended') {
        await deps.audioContext.value.resume()
      }
      const audioData = base64ToArrayBuffer(audioBase64)
      const pcm16 = new Int16Array(audioData)
      const float32 = new Float32Array(pcm16.length)

      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7fff)
      }

      const rate = resolvePlaybackRate(sampleRateHz)
      const audioBuffer = deps.audioContext.value.createBuffer(1, float32.length, rate)
      audioBuffer.getChannelData(0).set(float32)

      deps.audioQueue.push({ buffer: audioBuffer })
      scheduleQueuedChunks()
    } catch (error) {
      console.error('[KittyAgent] Audio playback error:', error)
    }
  }

  function stopAudioPlayback(): void {
    for (const source of [...scheduledSources]) {
      stopSource(source)
    }
    deps.currentAudioSource.value = null
    deps.audioQueue.length = 0
    nextPlayTime = 0
    deps.isPlaying.value = false
  }

  return { playAudioChunk, stopAudioPlayback }
}

export interface KittyCaptureDeps {
  isVoiceActive: Ref<boolean>
  ws: ShallowRef<WebSocket | null>
  audioContext: ShallowRef<AudioContext | null>
  micStream: ShallowRef<MediaStream | null>
  audioWorkletNode: ShallowRef<AudioWorkletNode | null>
  audioScriptProcessor: ShallowRef<ScriptProcessorNode | null>
  audioSource: ShallowRef<MediaStreamAudioSourceNode | null>
}

export function createKittyCapture(deps: KittyCaptureDeps) {
  async function startAudioCaptureFallback(): Promise<void> {
    if (!deps.audioContext.value || !deps.micStream.value) return

    const source = deps.audioContext.value.createMediaStreamSource(deps.micStream.value)
    const processor = deps.audioContext.value.createScriptProcessor(4096, 1, 1)

    processor.onaudioprocess = (e) => {
      if (
        !deps.isVoiceActive.value ||
        !deps.ws.value ||
        deps.ws.value.readyState !== WebSocket.OPEN
      ) {
        return
      }

      const inputData = e.inputBuffer.getChannelData(0)
      const pcm16 = new Int16Array(inputData.length)

      for (let i = 0; i < inputData.length; i++) {
        const s = Math.max(-1, Math.min(1, inputData[i]))
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
      }

      const audioBase64 = arrayBufferToBase64(pcm16.buffer)
      deps.ws.value.send(
        JSON.stringify({
          type: 'audio',
          data: audioBase64,
        })
      )
    }

    source.connect(processor)
    processor.connect(deps.audioContext.value.destination)
    deps.audioSource.value = source
    deps.audioScriptProcessor.value = processor
  }

  async function startAudioCapture(): Promise<void> {
    if (!deps.audioContext.value || !deps.micStream.value) {
      throw new Error('AudioContext or micStream not initialized')
    }

    if (deps.audioContext.value.state === 'suspended') {
      await deps.audioContext.value.resume()
    }

    try {
      await deps.audioContext.value.audioWorklet.addModule('/static/js/audio/pcm-processor.js')

      const source = deps.audioContext.value.createMediaStreamSource(deps.micStream.value)
      const workletNode = new AudioWorkletNode(deps.audioContext.value, 'pcm-processor')

      workletNode.port.onmessage = (event) => {
        if (
          !deps.isVoiceActive.value ||
          !deps.ws.value ||
          deps.ws.value.readyState !== WebSocket.OPEN
        ) {
          return
        }

        if (event.data.type === 'audio') {
          const audioBase64 = arrayBufferToBase64(event.data.data)
          deps.ws.value.send(
            JSON.stringify({
              type: 'audio',
              data: audioBase64,
            })
          )
        }
      }

      source.connect(workletNode)
      deps.audioWorkletNode.value = workletNode
      deps.audioSource.value = source
    } catch {
      console.warn('[KittyAgent] AudioWorklet not supported, falling back to ScriptProcessor')
      await startAudioCaptureFallback()
    }
  }

  return { startAudioCapture }
}
