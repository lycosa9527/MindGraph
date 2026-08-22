import { describe, expect, it, vi } from 'vitest'

const authFetchMock = vi.hoisted(() => vi.fn())

vi.mock('@/utils/api', () => ({
  authFetch: authFetchMock,
}))

import { fetchVoiceNoteHistoryDiagrams } from '@/composables/voiceNotes/fetchVoiceNoteHistory'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('fetchVoiceNoteHistoryDiagrams', () => {
  it('pages the filtered library API and does not request folders', async () => {
    authFetchMock.mockReset()
    authFetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          diagrams: [{ id: 'v1', title: 'voice recording_202608230012' }],
          total: 2,
          page: 1,
          page_size: 1,
          has_more: true,
          max_diagrams: 0,
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          diagrams: [{ id: 'v2', title: 'Renamed' }],
          total: 2,
          page: 2,
          page_size: 1,
          has_more: false,
          max_diagrams: 0,
        })
      )

    const rows = await fetchVoiceNoteHistoryDiagrams(1)

    expect(rows.map((row) => row.id)).toEqual(['v1', 'v2'])
    expect(authFetchMock).toHaveBeenCalledTimes(2)
    expect(String(authFetchMock.mock.calls[0]?.[0])).toBe(
      '/api/diagrams?page=1&page_size=1&source_channel=voice_notes'
    )
    expect(String(authFetchMock.mock.calls[1]?.[0])).toBe(
      '/api/diagrams?page=2&page_size=1&source_channel=voice_notes'
    )
  })
})
