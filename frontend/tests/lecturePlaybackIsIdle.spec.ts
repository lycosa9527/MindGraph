import { ref } from 'vue'

import { describe, expect, it, vi } from 'vitest'

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
