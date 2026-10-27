import { describe, expect, it } from 'vitest'

import {
  mindmateAvatarFileErrorKey,
  mindmateAvatarUploadErrorKey,
} from '@/utils/mindmateAvatarFile'
import {
  mergeCreatedMobileOrg,
  mobileOrgCardLabel,
  mobileOrgInviteClipboardText,
  parseMobileOrganizations,
} from '@/utils/mobileOrganizations'

describe('parseMobileOrganizations', () => {
  it('keeps invite identity and branding, and drops secrets', () => {
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
    expect(rows).toEqual([
      {
        id: 3,
        name: 'Demo',
        invitation_code: 'ABC-234',
        user_count: 2,
        display_name: null,
        mindmate_agent_name: null,
        mindmate_agent_alias: null,
        mindmate_agent_avatar_url: null,
      },
    ])
    expect(rows[0]).not.toHaveProperty('dify_api_key_masked')
    expect(rows[0]).not.toHaveProperty('token_stats')
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
      displayName: '',
      agentName: '',
      agentAlias: '',
      avatarUrl: '',
    })
  })

  it('fills a blank invite code on the refetched row', () => {
    const rows = mergeCreatedMobileOrg(
      [{ id: 9, name: 'New School', invitationCode: '', userCount: 0 }],
      { id: 9, name: 'New School', invitationCode: 'NEW-234' }
    )
    expect(rows[0]?.invitationCode).toBe('NEW-234')
  })

  it('keeps branding text and drops secrets', () => {
    const rows = parseMobileOrganizations([
      {
        id: 4,
        name: 'Demo',
        invitation_code: 'ABC-234',
        user_count: 1,
        display_name: ' 附中 ',
        mindmate_agent_name: ' 小思 ',
        mindmate_agent_alias: '思',
        mindmate_agent_avatar_url: ' /static/org_mindmate_avatars/4/avatar.png ',
        dify_api_key: 'sk-secret',
      },
    ])
    expect(rows[0]).toMatchObject({
      display_name: '附中',
      mindmate_agent_name: '小思',
      mindmate_agent_alias: '思',
      mindmate_agent_avatar_url: '/static/org_mindmate_avatars/4/avatar.png',
    })
    expect(rows[0]).not.toHaveProperty('dify_api_key')
  })

  it('shows the display name on the card when one is set', () => {
    expect(mobileOrgCardLabel({ name: '北京市第一中学', displayName: ' 附中 ' })).toBe('附中')
    expect(mobileOrgCardLabel({ name: '北京市第一中学', displayName: '  ' })).toBe('北京市第一中学')
  })

  it('checks avatar files before upload', () => {
    const png = new File([new Uint8Array([1, 2, 3])], 'a.png', { type: 'image/png' })
    expect(mindmateAvatarFileErrorKey(png)).toBeNull()
    const text = new File([new Uint8Array([1])], 'a.txt', { type: 'text/plain' })
    expect(mindmateAvatarFileErrorKey(text)).toBe('admin.schoolMindmateAvatarErrorType')
    expect(mindmateAvatarUploadErrorKey('mindmate_avatar_too_small')).toBe(
      'admin.schoolMindmateAvatarErrorTooSmall'
    )
    expect(mindmateAvatarUploadErrorKey('')).toBe('admin.schoolMindmateAvatarUploadFailed')
  })

  it('drops invalid rows and non-arrays', () => {
    expect(parseMobileOrganizations(null)).toEqual([])
    expect(parseMobileOrganizations([{ id: 0, name: 'Nope' }])).toEqual([])
    expect(parseMobileOrganizations([{ name: 'Nope' }])).toEqual([])
  })
})
