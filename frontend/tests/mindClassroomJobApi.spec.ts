import { describe, expect, it, vi } from 'vitest'

import {
  ClassroomJobsBusyError,
  classroomWatchResume,
  isClassroomJobPlayable,
  mindClassroomByDiagramPath,
  parseClassroomJobEnqueueError,
  watchMindClassroomJob,
} from '@/composables/mindMap/mindClassroomJobApi'
import { apiGet } from '@/utils/apiClient'

vi.mock('@/utils/apiClient', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}))

describe('mindClassroomJobApi watch', () => {
  it('looks up a diagram job by mode and LLM variant', () => {
    expect(mindClassroomByDiagramPath('diag-1', 'canvas_tour', 'qwen')).toBe(
      '/api/mind-classroom/jobs/by-diagram/diag-1?mode=canvas_tour&llm_model=qwen'
    )
    expect(mindClassroomByDiagramPath('diag-1', 'canvas_tour')).toBe(
      '/api/mind-classroom/jobs/by-diagram/diag-1?mode=canvas_tour'
    )
  })

  it('parses a 429 busy payload into the blocking job id', () => {
    const err = parseClassroomJobEnqueueError(
      JSON.stringify({
        detail: {
          message: 'Too many active classroom jobs (1/1). Wait or cancel.',
          job_id: 'job-busy',
        },
      }),
      429
    )
    expect(err).toBeInstanceOf(ClassroomJobsBusyError)
    expect((err as ClassroomJobsBusyError).jobId).toBe('job-busy')
  })

  it('resumes a dropped watch from the job snapshot', () => {
    expect(classroomWatchResume('ready')).toBe('ready')
    expect(classroomWatchResume('generating')).toBe('retry')
    expect(classroomWatchResume('queued')).toBe('retry')
    expect(classroomWatchResume('failed')).toBe('stop')
  })

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

  it('keeps watching while Postgres still says the job is generating', async () => {
    let sources = 0
    class FakeEventSource {
      static CLOSED = 2
      onmessage: ((event: MessageEvent) => void) | null = null
      onerror: (() => void) | null = null
      readyState = 1
      constructor(public url: string) {
        sources += 1
        queueMicrotask(() => {
          if (sources === 1) {
            this.readyState = 2
            this.onerror?.()
            return
          }
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
    vi.mocked(apiGet).mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'job-1', status: 'generating', progress: { done: 1 } }),
    } as Response)
    const updates: string[] = []
    const detail = await watchMindClassroomJob('job-1', {
      onUpdate: (next) => {
        updates.push(String(next.status))
      },
    })
    expect(detail.status).toBe('ready')
    expect(updates).toContain('generating')
    expect(sources).toBe(2)
    vi.unstubAllGlobals()
  })
})
