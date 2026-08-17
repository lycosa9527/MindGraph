import { describe, expect, it, vi } from 'vitest'

import { isClassroomJobPlayable, watchMindClassroomJob } from '@/composables/mindMap/mindClassroomJobApi'

describe('mindClassroomJobApi watch', () => {
  it('treats ready and partial as playable', () => {
    expect(isClassroomJobPlayable('ready')).toBe(true)
    expect(isClassroomJobPlayable('partial')).toBe(true)
    expect(isClassroomJobPlayable('generating')).toBe(false)
  })

  it('resolves from the first playable SSE snapshot without a timer', async () => {
    class FakeEventSource {
      static CLOSED = 2
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: (() => void) | null = null
      readyState = 1
      constructor(public url: string) {
        queueMicrotask(() => {
          this.onmessage?.({
            data: JSON.stringify({
              type: 'progress',
              job: {
                id: 'job-1',
                status: 'generating',
                progress: { in_flight: 2 },
              },
            }),
          } as MessageEvent)
          this.onmessage?.({
            data: JSON.stringify({
              type: 'progress',
              job: {
                id: 'job-1',
                status: 'ready',
                result_json: { steps: [{ id: 's1', caption: 'Hi' }] },
              },
            }),
          } as MessageEvent)
        })
      }
      close(): void {
        this.readyState = 2
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource)
    const updates: string[] = []
    const detail = await watchMindClassroomJob('job-1', {
      onUpdate: (next) => {
        updates.push(String(next.status))
      },
    })
    expect(detail.status).toBe('ready')
    expect(updates).toEqual(['generating', 'ready'])
    vi.unstubAllGlobals()
  })
})
