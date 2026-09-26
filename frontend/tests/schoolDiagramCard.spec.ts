import { describe, expect, it } from 'vitest'

import { schoolDiagramCardFromRow } from '@/utils/admin/schoolDiagramCard'

describe('schoolDiagramCardFromRow', () => {
  it('opens the usage diagram and keeps the unmasked invite code', () => {
    const card = schoolDiagramCardFromRow(
      {
        id: 9,
        name: '附中',
        invitation_code: '',
        user_count: 4,
        expires_at: '2027-01-01',
        show_chain_of_thought_oto: true,
      },
      { invitationCode: ' ABC-234 ', initialTab: 'usage' }
    )
    expect(card.id).toBe(9)
    expect(card.name).toBe('附中')
    expect(card.invitationCode).toBe('ABC-234')
    expect(card.user_count).toBe(4)
    expect(card.initial_tab).toBe('usage')
    expect(card.show_chain_of_thought).toBe(true)
    expect(card.dify_active_server).toBe(1)
  })

  it('keeps desktop defaults when numeric settings are missing', () => {
    const card = schoolDiagramCardFromRow({
      id: 2,
      name: 'Demo',
      dify_active_server: null,
      dify_timeout_seconds: '',
      extra_member_seats: null,
    })
    expect(card.dify_active_server).toBe(1)
    expect(card.dify_timeout_seconds).toBe(300)
    expect(card.extra_member_seats).toBe(0)
    expect(card.dingtalk_ai_card_streaming_max_chars).toBe(6500)
  })
})
