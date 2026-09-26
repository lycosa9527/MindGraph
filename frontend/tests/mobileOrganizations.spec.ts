import { describe, expect, it } from 'vitest'

import { mobileOrgInviteClipboardText, parseMobileOrganizations } from '@/utils/mobileOrganizations'

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

  it('asks for the full desktop share message', () => {
    const text = mobileOrgInviteClipboardText(
      (key, named) => `${key}|${named.orgName}|${named.siteUrl}|${named.code}`,
      { name: ' 北师大附中 ', invitationCode: ' ABC-234 ' },
      ' https://mindspring.example ',
      'Organization'
    )
    expect(text).toBe('admin.shareInviteMessage|北师大附中|https://mindspring.example|ABC-234')
  })

  it('skips copy text when the invite code is blank', () => {
    const text = mobileOrgInviteClipboardText(
      () => 'unused',
      { name: 'Demo', invitationCode: '  ' },
      'https://mindspring.example',
      'Organization'
    )
    expect(text).toBe('')
  })

  it('drops invalid rows and non-arrays', () => {
    expect(parseMobileOrganizations(null)).toEqual([])
    expect(parseMobileOrganizations([{ id: 0, name: 'Nope' }])).toEqual([])
    expect(parseMobileOrganizations([{ name: 'Nope' }])).toEqual([])
  })
})
