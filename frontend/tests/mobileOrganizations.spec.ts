import { describe, expect, it } from 'vitest'

import { parseMobileOrganizations } from '@/utils/mobileOrganizations'

describe('parseMobileOrganizations', () => {
  it('keeps only id, name, invite code, and member count', () => {
    const rows = parseMobileOrganizations([
      {
        id: 3,
        name: 'Demo',
        invitation_code: ' ABC-234 ',
        user_count: 2,
        token_stats: { total_tokens: 99 },
        dify_api_key_masked: 'sk-***',
        managers: ['alice@example.com'],
      },
    ])
    expect(rows).toEqual([{ id: 3, name: 'Demo', invitation_code: 'ABC-234', user_count: 2 }])
  })

  it('drops invalid rows and non-arrays', () => {
    expect(parseMobileOrganizations(null)).toEqual([])
    expect(parseMobileOrganizations([{ id: 0, name: 'Nope' }])).toEqual([])
    expect(parseMobileOrganizations([{ name: 'Nope' }])).toEqual([])
  })
})
