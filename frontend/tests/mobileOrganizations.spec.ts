import { describe, expect, it } from 'vitest'

import {
  mergeCreatedMobileOrg,
  mobileOrgInviteClipboardText,
  parseMobileOrganizations,
} from '@/utils/mobileOrganizations'

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

  it('places a new school in id order and keeps its invite code', () => {
    const rows = mergeCreatedMobileOrg(
      [{ id: 2, name: 'Older', invitationCode: 'OLD-234', userCount: 1 }],
      { id: 9, name: 'New School', invitationCode: ' NEW-234 ' }
    )
    expect(rows.map((row) => row.id)).toEqual([2, 9])
    expect(rows[1]).toEqual({
      id: 9,
      name: 'New School',
      invitationCode: 'NEW-234',
      userCount: 0,
    })
  })

  it('fills a blank invite code on the refetched row', () => {
    const rows = mergeCreatedMobileOrg(
      [{ id: 9, name: 'New School', invitationCode: '', userCount: 0 }],
      { id: 9, name: 'New School', invitationCode: 'NEW-234' }
    )
    expect(rows[0]?.invitationCode).toBe('NEW-234')
  })

  it('drops invalid rows and non-arrays', () => {
    expect(parseMobileOrganizations(null)).toEqual([])
    expect(parseMobileOrganizations([{ id: 0, name: 'Nope' }])).toEqual([])
    expect(parseMobileOrganizations([{ name: 'Nope' }])).toEqual([])
  })
})
