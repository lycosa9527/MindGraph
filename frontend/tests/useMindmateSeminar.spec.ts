import { beforeEach, describe, expect, it } from 'vitest'

import {
  MINDMATE_COLLAB_ACTIVE_ROOM_KEY,
  MINDMATE_COLLAB_JOINED_ROOMS_KEY,
  embeddedCollabRoomCode,
  forgetJoinedCollabRoom,
  hydrateEmbeddedCollabRoomCode,
  loadJoinedCollabRooms,
  rememberJoinedCollabRoom,
  setEmbeddedCollabRoomCode,
} from '@/composables/mindmate/mindmateSeminarEmbeddedBridge'
import { collabSocketCoversCode } from '@/composables/mindmate/mindmateSeminarLiveSession'
import { useMindmateSeminarPresenceBridge } from '@/composables/mindmate/mindmateSeminarPresenceBridge'
import {
  LOCAL_MINDMATE_COLLAB_SESSIONS_KEY,
  MINDMATE_COLLAB_ENDED_CODES_KEY,
  MINDMATE_COLLAB_SESSION_REMOVED_EVENT,
  formatMindmateSeminarCode,
  loadLocalMindmateSeminarSessions,
  markMindmateSeminarCodeEnded,
  normalizeMindmateSeminarCode,
  persistLocalMindmateSeminarSessions,
  shouldReconnectMindmateSeminar,
  trackLocalMindmateSeminarSession,
  wasMindmateSeminarCodeRecentlyEnded,
} from '@/utils/mindmateSeminarSessions'
import {
  mindmateSeminarStopSucceeded,
  removeLocalMindmateSeminarSessionByCode,
  resolveEndedMindmateSeminarSessionId,
  resolveMindmateSeminarSessionId,
  shouldRemoveCollabFromHistory,
  teardownMindmateSeminarClient,
} from '@/utils/mindmateSeminarTeardown'

describe('collabSocketCoversCode', () => {
  it('keeps the open seminar socket when the chat view comes back', () => {
    expect(collabSocketCoversCode('JWM-HEA', 'connected', 'jwmhea')).toBe(true)
    expect(collabSocketCoversCode('JWM-HEA', 'reconnecting', 'JWM-HEA')).toBe(true)
    expect(collabSocketCoversCode('JWM-HEA', 'connecting', 'JWM-HEA')).toBe(true)
  })

  it('does not reuse a socket that the owner already closed', () => {
    expect(collabSocketCoversCode('JWM-HEA', 'idle', 'JWM-HEA')).toBe(false)
    expect(collabSocketCoversCode('JWM-HEA', 'failed', 'JWM-HEA')).toBe(false)
    expect(collabSocketCoversCode('JWM-HEA', 'connected', 'AAA-BBB')).toBe(false)
    expect(collabSocketCoversCode(null, 'connected', 'JWM-HEA')).toBe(false)
  })
})

describe('shouldReconnectMindmateSeminar', () => {
  it('does not reconnect after idle shutdown 4010', () => {
    expect(shouldReconnectMindmateSeminar(4010)).toBe(false)
  })

  it('does not reconnect after host stop 4011', () => {
    expect(shouldReconnectMindmateSeminar(4011)).toBe(false)
  })

  it('does not reconnect after duplicate tab 4003', () => {
    expect(shouldReconnectMindmateSeminar(4003)).toBe(false)
  })

  it('reconnects on abnormal disconnect', () => {
    expect(shouldReconnectMindmateSeminar(1006)).toBe(true)
  })
})

describe('mindmate collab code helpers', () => {
  it('strips dash and uppercases', () => {
    expect(normalizeMindmateSeminarCode('abc-def')).toBe('ABCDEF')
  })

  it('formats code for navigation query', () => {
    expect(formatMindmateSeminarCode('abcdef')).toBe('ABC-DEF')
  })
})

describe('mindmate collab teardown helpers', () => {
  beforeEach(() => {
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(MINDMATE_COLLAB_ENDED_CODES_KEY)
  })

  it('shouldRemoveCollabFromHistory for ended sessions only', () => {
    expect(shouldRemoveCollabFromHistory('expired')).toBe(true)
    expect(shouldRemoveCollabFromHistory('host')).toBe(true)
    expect(shouldRemoveCollabFromHistory('left')).toBe(false)
  })

  it('teardown keeps sidebar history by default', () => {
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Public seminar',
        visibility: 'network',
      },
    ])
    teardownMindmateSeminarClient('abc-def')
    expect(loadLocalMindmateSeminarSessions()).toHaveLength(1)
  })

  it('teardown can drop history when room ended', () => {
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Public seminar',
      },
    ])
    teardownMindmateSeminarClient('abc-def', { removeFromHistory: true })
    expect(loadLocalMindmateSeminarSessions()).toHaveLength(0)
  })

  it('resolves session id from local storage by code', () => {
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-1',
        code: 'ABC-DEF',
        title: 'Seminar',
      },
    ])
    expect(resolveMindmateSeminarSessionId(null, 'abcdef')).toBe('sess-1')
    sessionStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  })

  it('does not archive a different live seminar when a sidebar code ends', () => {
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-live',
        code: 'XTB-CDR',
        title: 'Open seminar',
      },
      {
        session_id: 'sess-clicked',
        code: 'ABC-DEF',
        title: 'Clicked seminar',
      },
    ])
    expect(resolveEndedMindmateSeminarSessionId('sess-live', 'ABC-DEF')).toBe('sess-clicked')
    expect(resolveEndedMindmateSeminarSessionId('sess-clicked', 'ABC-DEF')).toBe('sess-clicked')
  })

  it('removes local session row by code', () => {
    persistLocalMindmateSeminarSessions([
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
    removeLocalMindmateSeminarSessionByCode('abc-def')
    expect(loadLocalMindmateSeminarSessions().map((row) => row.session_id)).toEqual(['sess-2'])
    sessionStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  })

  it('marks a removed room so the same code is not rejoined', () => {
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-1',
        code: 'CRK-G2H',
        title: 'Seminar',
      },
    ])
    removeLocalMindmateSeminarSessionByCode('crk-g2h')
    expect(wasMindmateSeminarCodeRecentlyEnded('CRK-G2H')).toBe(true)
    expect(wasMindmateSeminarCodeRecentlyEnded('XYZ-123')).toBe(false)
  })

  it('dispatches session-removed so sidebar org rows can evict', () => {
    const seen: string[] = []
    const onRemoved = (event: Event) => {
      const detail = (event as CustomEvent<{ code?: string }>).detail
      seen.push(String(detail?.code || ''))
    }
    window.addEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, onRemoved)
    persistLocalMindmateSeminarSessions([
      {
        session_id: 'sess-1',
        code: 'CRK-G2H',
        title: 'Seminar',
      },
    ])
    removeLocalMindmateSeminarSessionByCode('CRK-G2H')
    window.removeEventListener(MINDMATE_COLLAB_SESSION_REMOVED_EVENT, onRemoved)
    expect(seen).toEqual(['CRKG2H'])
  })
})

describe('mindmateSeminarStopSucceeded', () => {
  it('treats 404 as already ended', () => {
    expect(mindmateSeminarStopSucceeded(200)).toBe(true)
    expect(mindmateSeminarStopSucceeded(404)).toBe(true)
    expect(mindmateSeminarStopSucceeded(403)).toBe(false)
    expect(mindmateSeminarStopSucceeded(500)).toBe(false)
  })
})

describe('recently ended collab codes', () => {
  beforeEach(() => {
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
    localStorage.removeItem(MINDMATE_COLLAB_ENDED_CODES_KEY)
    sessionStorage.removeItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)
    sessionStorage.removeItem(MINDMATE_COLLAB_JOINED_ROOMS_KEY)
    embeddedCollabRoomCode.value = null
  })

  it('records an ended invite code', () => {
    markMindmateSeminarCodeEnded('abc-def')
    expect(wasMindmateSeminarCodeRecentlyEnded('ABCDEF')).toBe(true)
  })

  it('does not re-track a room that this tab just ended', () => {
    markMindmateSeminarCodeEnded('CRK-G2H')
    trackLocalMindmateSeminarSession({
      session_id: 'sess-1',
      code: 'CRK-G2H',
      title: 'Seminar',
    })
    expect(loadLocalMindmateSeminarSessions()).toHaveLength(0)
  })

  it('does not notify again when the same hosted room is re-tracked', () => {
    let changed = 0
    const onChanged = () => {
      changed += 1
    }
    window.addEventListener('mindmate-seminar-sessions-changed', onChanged)
    trackLocalMindmateSeminarSession({
      session_id: 'sess-hosted',
      code: '8K2-EUR',
      title: 'Seminar',
    })
    expect(changed).toBe(1)
    trackLocalMindmateSeminarSession({
      session_id: 'sess-hosted',
      code: '8K2EUR',
      title: 'Seminar (join)',
    })
    persistLocalMindmateSeminarSessions(loadLocalMindmateSeminarSessions())
    expect(changed).toBe(1)
    window.removeEventListener('mindmate-seminar-sessions-changed', onChanged)
  })

  it('does not reopen an embedded room that this tab just ended', () => {
    markMindmateSeminarCodeEnded('CRK-G2H')
    setEmbeddedCollabRoomCode('CRK-G2H')
    expect(embeddedCollabRoomCode.value).toBeNull()
    setEmbeddedCollabRoomCode(null)
    expect(embeddedCollabRoomCode.value).toBeNull()
    expect(sessionStorage.getItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)).toBeNull()
  })

  it('remembers the open seminar so a reload can rejoin the live socket', () => {
    setEmbeddedCollabRoomCode('jwmhea')
    expect(embeddedCollabRoomCode.value).toBe('JWM-HEA')
    expect(sessionStorage.getItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)).toBe('JWM-HEA')
    embeddedCollabRoomCode.value = null
    hydrateEmbeddedCollabRoomCode()
    expect(embeddedCollabRoomCode.value).toBe('JWM-HEA')
  })

  it('does not restore a seminar this tab just ended', () => {
    setEmbeddedCollabRoomCode('JWM-HEA')
    markMindmateSeminarCodeEnded('JWM-HEA')
    embeddedCollabRoomCode.value = null
    hydrateEmbeddedCollabRoomCode()
    expect(embeddedCollabRoomCode.value).toBeNull()
    expect(sessionStorage.getItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)).toBeNull()
  })

  it('persists ended codes so another tab can see them', () => {
    markMindmateSeminarCodeEnded('8KZ-BAW')
    const stored = JSON.parse(
      localStorage.getItem(MINDMATE_COLLAB_ENDED_CODES_KEY) || '{}'
    ) as Record<string, number>
    expect(typeof stored['8KZBAW']).toBe('number')
  })

  it('hydrates ended codes from localStorage', () => {
    localStorage.setItem(MINDMATE_COLLAB_ENDED_CODES_KEY, JSON.stringify({ QWERT1: Date.now() }))
    expect(wasMindmateSeminarCodeRecentlyEnded('QWE-RT1')).toBe(true)
  })

  it('remembers every seminar this tab joined', () => {
    rememberJoinedCollabRoom('mmm111')
    rememberJoinedCollabRoom('NNN-222')
    rememberJoinedCollabRoom('mmm-111')
    expect(loadJoinedCollabRooms()).toEqual(['NNN-222', 'MMM-111'])
    forgetJoinedCollabRoom('nnn222')
    expect(loadJoinedCollabRooms()).toEqual(['MMM-111'])
  })

  it('does not remember a seminar this tab just ended', () => {
    markMindmateSeminarCodeEnded('MMM-111')
    rememberJoinedCollabRoom('MMM-111')
    expect(loadJoinedCollabRooms()).toEqual([])
  })

  it('ending one seminar leaves the other seminar selected', () => {
    setEmbeddedCollabRoomCode('PPP-333')
    rememberJoinedCollabRoom('PPP-333')
    rememberJoinedCollabRoom('QQQ-444')
    teardownMindmateSeminarClient('QQQ-444', { removeFromHistory: true })
    expect(embeddedCollabRoomCode.value).toBe('PPP-333')
    expect(loadJoinedCollabRooms()).toEqual(['PPP-333'])
    expect(sessionStorage.getItem(MINDMATE_COLLAB_ACTIVE_ROOM_KEY)).toBe('PPP-333')
  })

  it('ending the visible seminar clears only that selection', () => {
    setEmbeddedCollabRoomCode('RRR-555')
    rememberJoinedCollabRoom('RRR-555')
    rememberJoinedCollabRoom('SSS-666')
    teardownMindmateSeminarClient('rrr-555', { removeFromHistory: true })
    expect(embeddedCollabRoomCode.value).toBeNull()
    expect(loadJoinedCollabRooms()).toEqual(['SSS-666'])
  })

  it('leaving the seminar view keeps its socket remembered', () => {
    setEmbeddedCollabRoomCode('TTT-777')
    rememberJoinedCollabRoom('TTT-777')
    rememberJoinedCollabRoom('UUU-888')
    teardownMindmateSeminarClient('TTT-777')
    expect(embeddedCollabRoomCode.value).toBeNull()
    expect(loadJoinedCollabRooms()).toEqual(['TTT-777', 'UUU-888'])
  })

  it('teardown does not wipe org presence', () => {
    const { updatePresence, onlineUserIds } = useMindmateSeminarPresenceBridge()
    updatePresence(5, 'active')
    teardownMindmateSeminarClient('QWE-RT1', { removeFromHistory: true })
    expect(onlineUserIds.value.has(5)).toBe(true)
  })

  it('replaces the online set from a snapshot and keeps a just-arrived active', () => {
    const {
      applyPresenceSnapshot,
      updatePresence,
      onlineUserIds,
      lastSeenOnlineAtByUserId,
      presenceReady,
    } = useMindmateSeminarPresenceBridge()
    expect(presenceReady.value).toBe(false)
    updatePresence(71, 'active', 1_000)
    updatePresence(72, 'active', 1_000)
    expect(presenceReady.value).toBe(false)
    applyPresenceSnapshot([71], undefined, 11_000)
    expect(presenceReady.value).toBe(true)
    expect(onlineUserIds.value.has(71)).toBe(true)
    expect(onlineUserIds.value.has(72)).toBe(false)
    expect(lastSeenOnlineAtByUserId.value[72]).toBe(11_000)
    updatePresence(73, 'active', 20_000)
    applyPresenceSnapshot([71], undefined, 20_100)
    expect(onlineUserIds.value.has(73)).toBe(true)
    expect(onlineUserIds.value.has(71)).toBe(true)
    updatePresence(73, 'offline', 21_000)
    expect(onlineUserIds.value.has(73)).toBe(false)
    expect(lastSeenOnlineAtByUserId.value[73]).toBe(21_000)
    updatePresence(73, 'active', 22_000)
    expect(lastSeenOnlineAtByUserId.value[73]).toBeUndefined()
  })
})
