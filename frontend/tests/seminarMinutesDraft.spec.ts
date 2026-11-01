import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequestJson } from '@/utils/apiClient'
import { requestSeminarMinutesDraft } from '@/utils/mindmateSeminarMinutes'

vi.mock('@/utils/apiClient', () => ({
  apiRequestJson: vi.fn(),
}))

describe('requestSeminarMinutesDraft', () => {
  beforeEach(() => {
    vi.mocked(apiRequestJson).mockReset()
  })

  it('posts the seminar slice to the minutes route', async () => {
    vi.mocked(apiRequestJson).mockResolvedValue({ text: '{"consensus":["先改导入"]}' })
    const text = await requestSeminarMinutesDraft('room 1', {
      zh: true,
      topic: '导入',
      goals: ['先改导入'],
      speakers: '王雅萱',
      observers: '',
      files: [],
      quotes: [],
      transcript: '王雅萱：先改导入',
    })
    expect(text).toBe('{"consensus":["先改导入"]}')
    const [url, options] = vi.mocked(apiRequestJson).mock.calls[0]
    expect(url).toBe('/api/mindmate/seminar/room%201/minutes')
    expect(options).toMatchObject({ method: 'POST' })
    const body = JSON.parse(String(options?.body)) as { transcript: string; zh: boolean }
    expect(body.zh).toBe(true)
    expect(body.transcript).toBe('王雅萱：先改导入')
  })
})
