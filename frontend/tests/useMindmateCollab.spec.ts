import { beforeEach, describe, expect, it } from 'vitest'

import { setEmbeddedCollabRoomCode, embeddedCollabRoomCode } from '@/composables/mindmate/mindmateCollabEmbeddedBridge'
import { useMindmateCollabPresenceBridge } from '@/composables/mindmate/mindmateCollabPresenceBridge'
import {
  formatMindmateCollabCode,
  loadLocalMindmateCollabSessions,
  LOCAL_MINDMATE_COLLAB_SESSIONS_KEY,
  markMindmateCollabCodeEnded,
  MINDMATE_COLLAB_ENDED_CODES_KEY,
  MINDMATE_COLLAB_SESSION_REMOVED_EVENT,
  normalizeMindmateCollabCode,
  persistLocalMindmateCollabSessions,
  shouldReconnectMindmateCollab,
  trackLocalMindmateCollabSession,
  wasMindmateCollabCodeRecentlyEnded,
} from '@/utils/mindmateCollabSessions'
import {
  mindmateCollabStopSucceeded,
  removeLocalMindmateCollabSessionByCode,
  resolveMindmateCollabSessionId,
  shouldRemoveCollabFromHistory,
  teardownMindmateCollabClient,
} from '@/utils/mindmateCollabTeardown'

describe('shouldReconnectMindmateCollab', () => {
  it('does not reconnect after idle shutdown 4010', () => {
    expect(shouldReconnectMindmateCollab(4010)).toBe(false)
  })

  it('does not reconnect after host stop 4011', () => {
    expect(shouldReconnectMindmateCollab(4011)).toBe(false)
  })

  it('does not reconnect after duplicate tab 4003', () => {
    expect(shouldReconnectMindmateCollab(4003)).toBe(false)
  })

  it('reconnects on abnormal disconnect', () => {
    expect(shouldReconnectMindmateCollab(1006)).toBe(true)
  })
})

describe('mindmate collab code helpers', () => {
  it('strips dash and uppercases', () => {
    expect(normalizeMindmateCollabCode('abc-def')).toBe('ABCDEF')
  })

  it('formats code for navigation query', () => {
    expect(formatMindmateCollabCode('abcdef')).toBe('ABC-DEF')
  })
})

describe('mindmate collab teardown helpers', () => {
  beforeEach(() => {
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(MINDMATE_COLLAB_ENDED_CODES_KEY)
  })

  it('shouldRemoveCollabFromHistory for ended sessions only', () => {
    expect(shouldRemoveCollabFromHistory('idle')).toBe(true)
    expect(shouldRemoveCollabFromHistory('host')).toBe(true)
    expect(shouldRemoveCollabFromHistory('left')).toBe(false)
  })

  it('teardown keeps sidebar history by default', () => {
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Public seminar',
        visibility: 'network',
      },
    ])
    teardownMindmateCollabClient('abc-def')
    expect(loadLocalMindmateCollabSessions()).toHaveLength(1)
  })

  it('teardown can drop history when room ended', () => {
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Public seminar',
      },
    ])
    teardownMindmateCollabClient('abc-def', { removeFromHistory: true })
    expect(loadLocalMindmateCollabSessions()).toHaveLength(0)
  })

  it('resolves session id from local storage by code', () => {
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Seminar',
      },
    ])
    expect(resolveMindmateCollabSessionId(null, 'abcdef')).toBe('sess-1')
    sessionStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  })

  it('removes local session row by code', () => {
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Seminar',
      },
      {
        session_id: 'sess-2',
        code: 'XYZ-123',
        title: 'Other',
      },
    ])
    removeLocalMindmateCollabSessionByCode('abc-def')
    expect(loadLocalMindmateCollabSessions().map((row) => row.session_id)).toEqual(['sess-2'])
    sessionStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  })

  it('marks a removed room so the same code is not rejoined', () => {
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'CRK-G2H',
        title: 'Seminar',
      },
    ])
    removeLocalMindmateCollabSessionByCode('crk-g2h')
    expect(wasMindmateCollabCodeRecentlyEnded('CRK-G2H')).toBe(true)
    expect(wasMindmateCollabCodeRecentlyEnded('XYZ-123')).toBe(false)
  })

  it('dispatches session-removed so sidebar org rows can evict', () => {
    const seen: string[] = []
    const onRemoved = (event: Event) => {
      const detail = (event as CustomEvent<{ code?: string }>).detail
      seen.push(String(detail?.code || ''))
    }
    window.addEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, onRemoved)
    persistLocalMindmateCollabSessions([
      {
        session_id: 'sess-1',
        code: 'CRK-G2H',
        title: 'Seminar',
      },
    ])
    removeLocalMindmateCollabSessionByCode('CRK-G2H')
    window.removeEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, onRemoved)
    expect(seen).toEqual(['CRKG2H'])
  })
})

describe('mindmateCollabStopSucceeded', () => {
  it('treats 404 as already ended', () => {
    expect(mindmateCollabStopSucceeded(200)).toBe(true)
    expect(mindmateCollabStopSucceeded(404)).toBe(true)
    expect(mindmateCollabStopSucceeded(403)).toBe(false)
    expect(mindmateCollabStopSucceeded(500)).toBe(false)
  })
})

describe('recently ended collab codes', () => {
  beforeEach(() => {
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(MINDMATE_COLLAB_ENDED_CODES_KEY)
    embeddedCollabRoomCode.value = null
  })

  it('records an ended invite code', () => {
    markMindmateCollabCodeEnded('abc-def')
    expect(wasMindmateCollabCodeRecentlyEnded('ABCDEF')).toBe(true)
  })

  it('does not re-track a room that this tab just ended', () => {
    markMindmateCollabCodeEnded('CRK-G2H')
    trackLocalMindmateCollabSession({
      session_id: 'sess-1',
      code: 'CRK-G2H',
      title: 'Seminar',
    })
    expect(loadLocalMindmateCollabSessions()).toHaveLength(0)
  })

  it('does not reopen an embedded room that this tab just ended', () => {
    markMindmateCollabCodeEnded('CRK-G2H')
    setEmbeddedCollabRoomCode('CRK-G2H')
    expect(embeddedCollabRoomCode.value).toBeNull()
    setEmbeddedCollabRoomCode(null)
    expect(embeddedCollabRoomCode.value).toBeNull()
  })

  it('persists ended codes so another tab can see them', () => {
    markMindmateCollabCodeEnded('8KZ-BAW')
    const stored = JSON.parse(localStorage.getItem(MINDMATE_COLLAB_ENDED_CODES_KEY) || '{}') as Record<
      string,
      number
    >
    expect(typeof stored['8KZBAW']).toBe('number')
  })

  it('hydrates ended codes from localStorage', () => {
    localStorage.setItem(
      MINDMATE_COLLAB_ENDED_CODES_KEY,
      JSON.stringify({ QWERT1: Date.now() }),
    )
    expect(wasMindmateCollabCodeRecentlyEnded('QWE-RT1')).toBe(true)
  })

  it('teardown does not wipe org presence', () => {
    const { updatePresence, onlineUserIds } = useMindmateCollabPresenceBridge()
    updatePresence(5, 'active')
    teardownMindmateCollabClient('QWE-RT1', { removeFromHistory: true })
    expect(onlineUserIds.value.has(5)).toBe(true)
  })
})
