import { describe, expect, it } from 'vitest'

import { mindmatePresenceSubscribeMessage } from '@/composables/social/useMindmateSeminarNotify'

describe('mindmatePresenceSubscribeMessage', () => {
  it('omits org_id when the school is not known yet', () => {
    expect(JSON.parse(mindmatePresenceSubscribeMessage(null))).toEqual({
      type: 'subscribe_presence',
    })
  })

  it('includes org_id when the school is known', () => {
    expect(JSON.parse(mindmatePresenceSubscribeMessage(12))).toEqual({
      type: 'subscribe_presence',
      org_id: 12,
    })
  })
})
