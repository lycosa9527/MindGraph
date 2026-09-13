import { ref } from 'vue'

import { describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  handleKittyServerMessage,
  lecturePlaybackIsIdle,
} from '@/composables/kitty/kittyAgentInbound'

describe('lecturePlaybackIsIdle', () => {
  it('waits until synthesis, decode, and queued PCM are all finished', () => {
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 0,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(true)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 0,
        scheduledCount: 1,
        queuedCount: 0,
      })
    ).toBe(false)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: true,
        decodeInFlight: 1,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(false)
    expect(
      lecturePlaybackIsIdle({
        synthesisDone: false,
        decodeInFlight: 0,
        scheduledCount: 0,
        queuedCount: 0,
      })
    ).toBe(false)
  })

  it('only treats lecture tts_done as lecture synthesis complete', () => {
    const marked: string[] = []
    const deps = {
      destroyed: () => false,
      cleaningUp: () => false,
      isVoiceActive: ref(false),
      state: ref<'active' | 'speaking' | 'listening' | 'idle' | 'connecting' | 'error'>('speaking'),
      sessionId: ref<string | null>('sid'),
      lastTranscription: ref<string | null>(null),
      lastError: ref<string | null>(null),
      playAudioChunk: vi.fn(async () => undefined),
      stopAudioPlayback: vi.fn(),
      markLectureSynthesisDone: (stepId?: string) => {
        marked.push(stepId ?? '')
      },
    }
    handleKittyServerMessage({ type: 'tts_done', step_id: 'chat' }, deps)
    expect(marked).toEqual([])
    handleKittyServerMessage({ type: 'tts_done', lecture: true, step_id: 's1' }, deps)
    expect(marked).toEqual(['s1'])
  })
})

describe('handleKittyServerMessage push-on-write', () => {
  it('emits live_context, conversation_turn, and session_snapshot', () => {
    const emitted: string[] = []
    const onLive = () => {
      emitted.push('live')
    }
    const onTurn = () => {
      emitted.push('turn')
    }
    const onSnap = () => {
      emitted.push('snap')
    }
    eventBus.on('kitty:live_context_update', onLive)
    eventBus.on('kitty:conversation_turn', onTurn)
    eventBus.on('kitty:session_snapshot', onSnap)
    const deps = {
      destroyed: () => false,
      cleaningUp: () => false,
      isVoiceActive: ref(false),
      state: ref<'active' | 'speaking' | 'listening' | 'idle' | 'connecting' | 'error'>('active'),
      sessionId: ref<string | null>('sid'),
      lastTranscription: ref<string | null>(null),
      lastError: ref<string | null>(null),
      playAudioChunk: vi.fn(async () => undefined),
      stopAudioPlayback: vi.fn(),
    }
    handleKittyServerMessage(
      { type: 'live_context_update', scope: 'lib-1', ok: true, diagram_type: 'mindmap' },
      deps
    )
    handleKittyServerMessage(
      {
        type: 'conversation_turn',
        scope: 'lib-1',
        turn: { turn_id: 't1', role: 'kitty', content: 'ok' },
      },
      deps
    )
    handleKittyServerMessage(
      {
        type: 'session_snapshot',
        session: { requested_scope: 'lib-1', canvas_owner_present: true },
      },
      deps
    )
    expect(emitted).toEqual(['live', 'turn', 'snap'])
    eventBus.off('kitty:live_context_update', onLive)
    eventBus.off('kitty:conversation_turn', onTurn)
    eventBus.off('kitty:session_snapshot', onSnap)
  })
})
