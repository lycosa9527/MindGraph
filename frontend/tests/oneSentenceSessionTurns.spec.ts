import { describe, expect, it, vi, afterEach } from 'vitest'

import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'

describe('useOneSentenceSessionTurns', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchOneSentenceTurns returns user and kitty rows', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ok: true,
          turns: [
            { turn_id: 'a', role: 'user', content: '主题', phase: 'create', source: 'ui_create', ts: 1 },
            { turn_id: 'b', role: 'kitty', content: '好的', phase: 'create', source: 'ui_create', ts: 2 },
            { turn_id: 'c', role: 'meta', content: '', phase: 'edit', source: 'route', ts: 3 },
          ],
        }),
      })
    )

    const rows = await fetchOneSentenceTurns('diagram-1')
    expect(rows).toHaveLength(2)
    expect(rows[0]?.role).toBe('user')
  })

  it('appendOneSentenceTurn posts a single turn', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    vi.stubGlobal('fetch', fetchMock)

    const ok = await appendOneSentenceTurn('diagram-1', {
      role: 'user',
      content: '北京三日游',
      phase: 'create',
      source: 'ui_create',
    })

    expect(ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/kitty/one_sentence/diagram-1/turns',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('fetchOneSentenceTurns returns empty on HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    const rows = await fetchOneSentenceTurns('diagram-1')
    expect(rows).toEqual([])
  })

  it('migrateOneSentenceScope posts scope pair', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    vi.stubGlobal('fetch', fetchMock)

    const ok = await migrateOneSentenceScope('ephemeral-1', 'library-2')
    expect(ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/kitty/one_sentence/migrate_scope',
      expect.objectContaining({ method: 'POST' })
    )
  })
})
