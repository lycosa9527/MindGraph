import type { Ref, ShallowRef } from 'vue'

import { type EventTypes, eventBus } from '@/composables/core/useEventBus'
import {
  applyKittyDiagramUpdate,
  executeKittyAgentAction,
} from '@/composables/kitty/kittyAgentActions'
import { arrayBufferToBase64, base64ToArrayBuffer } from '@/composables/kitty/kittyAgentAudioCodec'
import {
  formatKittyDiagramUpdateDebug,
  normalizeKittyDebugText,
} from '@/composables/kitty/kittyAgentDebug'
import type { KittyAgentState } from '@/composables/kitty/kittyAgentTypes'

export interface KittyInboundHandlerDeps {
  destroyed: () => boolean
  cleaningUp: () => boolean
  isVoiceActive: Ref<boolean>
  state: Ref<KittyAgentState>
  sessionId: Ref<string | null>
  lastTranscription: Ref<string | null>
  lastError: Ref<string | null>
  onTranscription?: (text: string) => void
  onTextChunk?: (text: string) => void
  onError?: (error: string) => void
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
      deps.onTranscription?.(String(data.text ?? ''))
      deps.state.value = deps.isVoiceActive.value ? 'listening' : 'active'
      break

    case 'text_chunk':
      if (deps.isVoiceActive.value) break
      eventBus.emit('voice:text_chunk', { text: String(data.text ?? '') })
      deps.onTextChunk?.(String(data.text ?? ''))
      break

    case 'audio_chunk':
      if (!deps.destroyed() && !deps.cleaningUp() && !deps.isVoiceActive.value) {
        void deps.playAudioChunk(String(data.audio ?? ''))
        deps.state.value = 'speaking'
      }
      break

    case 'speech_started':
      eventBus.emit('voice:speech_started', {
        audioStartMs: typeof data.audio_start_ms === 'number' ? data.audio_start_ms : undefined,
      })
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
      executeKittyAgentAction(String(data.action ?? ''), (data.params as Record<string, unknown>) ?? {})
      break

    case 'diagram_update': {
      const diagramAction = String(data.action ?? '')
      const diagramUpdates = (data.updates as Record<string, unknown>) ?? {}
      eventBus.emit('voice:diagram_update_executed', {
        action: diagramAction,
        updates: diagramUpdates,
        summary: formatKittyDiagramUpdateDebug(diagramAction, diagramUpdates),
      })
      applyKittyDiagramUpdate(diagramAction, diagramUpdates)
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
    if (deps.destroyed() || !deps.audioContext.value || deps.audioContext.value.state === 'closed') {
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
      if (!deps.isVoiceActive.value || !deps.ws.value || deps.ws.value.readyState !== WebSocket.OPEN) {
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
        if (!deps.isVoiceActive.value || !deps.ws.value || deps.ws.value.readyState !== WebSocket.OPEN) {
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
