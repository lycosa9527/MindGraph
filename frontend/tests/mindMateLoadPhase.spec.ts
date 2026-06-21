import { describe, expect, it } from 'vitest'

import {
  isActiveLlmPhaseRing,
  isLlmGenerating,
} from '@/utils/llmLoadPhase'
import {
  mindMateLoadPhaseOnAbort,
  mindMateLoadPhaseOnComplete,
  mindMateLoadPhaseOnError,
  mindMateLoadPhaseOnFirstToken,
  mindMateLoadPhaseOnSendStart,
  mindMateLoadPhaseOnStreamOpen,
} from '@/composables/mindmate/mindMateLoadPhase'
import { consumeSseDataLines } from '@/utils/mindMateSseStream'

describe('llmLoadPhase utils', () => {
  it('detects generating and active ring phases', () => {
    expect(isLlmGenerating('sending')).toBe(true)
    expect(isLlmGenerating('waiting')).toBe(true)
    expect(isLlmGenerating('streaming')).toBe(true)
    expect(isLlmGenerating('idle')).toBe(false)
    expect(isLlmGenerating('error')).toBe(false)

    expect(isActiveLlmPhaseRing('sending')).toBe(true)
    expect(isActiveLlmPhaseRing('waiting')).toBe(true)
    expect(isActiveLlmPhaseRing('streaming')).toBe(true)
    expect(isActiveLlmPhaseRing('idle')).toBe(false)
  })
})

describe('mindMateLoadPhase helpers', () => {
  it('maps lifecycle transitions to canvas-aligned phases', () => {
    expect(mindMateLoadPhaseOnSendStart()).toBe('sending')
    expect(mindMateLoadPhaseOnStreamOpen()).toBe('waiting')
    expect(mindMateLoadPhaseOnFirstToken()).toBe('streaming')
    expect(mindMateLoadPhaseOnComplete()).toBe('idle')
    expect(mindMateLoadPhaseOnAbort()).toBe('idle')
    expect(mindMateLoadPhaseOnError()).toBe('error')
  })

  it('follows send → waiting → streaming → idle sequence', () => {
    let phase = mindMateLoadPhaseOnSendStart()
    expect(phase).toBe('sending')
    expect(isLlmGenerating(phase)).toBe(true)

    phase = mindMateLoadPhaseOnStreamOpen()
    expect(phase).toBe('waiting')

    phase = mindMateLoadPhaseOnFirstToken()
    expect(phase).toBe('streaming')

    phase = mindMateLoadPhaseOnComplete()
    expect(phase).toBe('idle')
    expect(isLlmGenerating(phase)).toBe(false)
  })

  it('stop maps to idle like abort helper', () => {
    expect(mindMateLoadPhaseOnAbort()).toBe('idle')
    expect(isActiveLlmPhaseRing(mindMateLoadPhaseOnAbort())).toBe(false)
  })
})

describe('consumeSseDataLines', () => {
  it('buffers partial SSE lines across chunks', async () => {
    const encoder = new TextEncoder()
    let readCount = 0
    const chunks = [
      encoder.encode('data: {"event":"message","answer":"Hel'),
      encoder.encode('lo"}\n\n'),
    ]
    const reader = {
      read: async () => {
        if (readCount >= chunks.length) {
          return { done: true, value: undefined }
        }
        const value = chunks[readCount]
        readCount += 1
        return { done: false, value }
      },
      releaseLock: () => undefined,
    } as ReadableStreamDefaultReader<Uint8Array>

    const events: Record<string, unknown>[] = []
    await consumeSseDataLines(reader, (payload) => {
      events.push(payload)
    })

    expect(events).toHaveLength(1)
    expect(events[0]).toEqual({ event: 'message', answer: 'Hello' })
  })

  it('stops when handler returns false', async () => {
    const encoder = new TextEncoder()
    const payload = encoder.encode('data: {"event":"error","message":"fail"}\n\n')
    let readOnce = false
    const reader = {
      read: async () => {
        if (readOnce) {
          return { done: true, value: undefined }
        }
        readOnce = true
        return { done: false, value: payload }
      },
      releaseLock: () => undefined,
    } as ReadableStreamDefaultReader<Uint8Array>

    let calls = 0
    await consumeSseDataLines(reader, () => {
      calls += 1
      return false
    })

    expect(calls).toBe(1)
  })
})
