import { beforeEach, describe, expect, it } from 'vitest'

import {
  formatMindmateCollabCode,
  loadLocalMindmateCollabSessions,
  LOCAL_MINDMATE_COLLAB_SESSIONS_KEY,
  normalizeMindmateCollabCode,
  persistLocalMindmateCollabSessions,
  shouldReconnectMindmateCollab,
} from '@/utils/mindmateCollabSessions'
import {
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
})
