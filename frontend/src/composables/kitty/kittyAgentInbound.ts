import type { Ref, ShallowRef } from 'vue'

import { type EventTypes, eventBus } from '@/composables/core/useEventBus'
import { executeKittyAgentAction } from '@/composables/kitty/kittyAgentActions'
import type { DiagramEditExpectedEffect } from '@/utils/diagramEditVerify'
import { arrayBufferToBase64, base64ToArrayBuffer } from '@/composables/kitty/kittyAgentAudioCodec'
import { normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'
import type { KittyAgentState } from '@/composables/kitty/kittyAgentTypes'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import { useKittySessionStore } from '@/stores/kittySession'

export interface KittyInboundHandlerDeps {
  destroyed: () => boolean
  cleaningUp: () => boolean
  textOnly?: boolean
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
  playAudioChunk: (audioBase64: string) => Promise<void>
  stopAudioPlayback: () => void
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
          void deps.playAudioChunk(String(data.audio ?? ''))
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
        kittySession.setAsrPartialTranscript(text)
        eventBus.emit('kitty:asr_partial', { text })
      }
      break

    case 'asr_final':
      {
        const kittySession = useKittySessionStore()
        const text = String(data.text ?? '')
        kittySession.setAsrPartialTranscript(text)
        eventBus.emit('kitty:asr_final', { text })
      }
      break

    case 'asr_started':
      useKittySessionStore().setAsrListening(true)
      eventBus.emit('kitty:asr_started', {})
      break

    case 'asr_stopped':
      useKittySessionStore().setAsrListening(false)
      eventBus.emit('kitty:asr_stopped', {})
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
        beforeRaw &&
        Array.isArray(beforeRaw.nodes) &&
        Array.isArray(beforeRaw.connections)
          ? {
              nodes: beforeRaw.nodes as import('@/types').DiagramNode[],
              connections: beforeRaw.connections as import('@/types').Connection[],
            }
          : undefined

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
        lane: 'mobile',
      })
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
  sampleRate: number
  audioContext: ShallowRef<AudioContext | null>
  isVoiceActive: Ref<boolean>
  isPlaying: Ref<boolean>
  state: Ref<KittyAgentState>
  currentAudioSource: ShallowRef<AudioBufferSourceNode | null>
  audioQueue: Array<{ buffer: AudioBuffer }>
}

export function createKittyPlayback(deps: KittyPlaybackDeps) {
  async function playAudioChunk(audioBase64: string): Promise<void> {
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

      const audioBuffer = deps.audioContext.value.createBuffer(1, float32.length, deps.sampleRate)
      audioBuffer.getChannelData(0).set(float32)

      deps.audioQueue.push({ buffer: audioBuffer })

      if (!deps.isPlaying.value) {
        playNextAudio()
      }
    } catch (error) {
      console.error('[KittyAgent] Audio playback error:', error)
    }
  }

  function playNextAudio(): void {
    if (
      deps.destroyed() ||
      !deps.audioContext.value ||
      deps.audioContext.value.state === 'closed'
    ) {
      deps.isPlaying.value = false
      deps.currentAudioSource.value = null
      deps.audioQueue.length = 0
      return
    }

    if (deps.audioQueue.length === 0) {
      deps.isPlaying.value = false
      deps.currentAudioSource.value = null
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      return
    }

    if (deps.isVoiceActive.value) {
      deps.audioQueue.length = 0
      deps.isPlaying.value = false
      deps.currentAudioSource.value = null
      deps.state.value = 'listening'
      return
    }

    deps.isPlaying.value = true
    deps.state.value = 'speaking'

    const chunk = deps.audioQueue.shift()
    if (!chunk) return

    const source = deps.audioContext.value.createBufferSource()
    source.buffer = chunk.buffer
    source.connect(deps.audioContext.value.destination)

    deps.currentAudioSource.value = source

    source.onended = () => {
      if (deps.destroyed()) {
        deps.currentAudioSource.value = null
        deps.isPlaying.value = false
        return
      }
      deps.currentAudioSource.value = null
      playNextAudio()
    }

    source.start()
  }

  function stopAudioPlayback(): void {
    if (deps.currentAudioSource.value) {
      try {
        deps.currentAudioSource.value.onended = null
        deps.currentAudioSource.value.stop()
        deps.currentAudioSource.value.disconnect()
      } catch {
        /* already stopped */
      }
      deps.currentAudioSource.value = null
    }
    deps.audioQueue.length = 0
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
