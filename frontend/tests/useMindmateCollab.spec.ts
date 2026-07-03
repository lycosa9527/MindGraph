import { describe, expect, it } from 'vitest'

import {
  formatMindmateCollabCode,
  normalizeMindmateCollabCode,
  shouldReconnectMindmateCollab,
} from '@/utils/mindmateCollabSessions'

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
