import { describe, expect, it } from 'vitest'

import {
  buildPrivatizedColumnFilters,
  filterOrgByPrivatized,
  isOrgPrivatized,
} from '@/utils/orgPrivatization'

describe('isOrgPrivatized', () => {
  it('uses API is_privatized when present', () => {
    expect(isOrgPrivatized({ is_privatized: true })).toBe(true)
    expect(isOrgPrivatized({ is_privatized: false, dify_api_key_masked: '****' })).toBe(false)
  })

  it('falls back to raw fields when is_privatized is missing', () => {
    expect(isOrgPrivatized({})).toBe(false)
    expect(isOrgPrivatized({ mindmate_agent_name: '小助手' })).toBe(false)
    expect(isOrgPrivatized({ mindmate_agent_avatar_url: '/static/org_mindmate_avatars/1/avatar.png' })).toBe(
      false
    )
    expect(isOrgPrivatized({ dify_api_key_masked: 'app-****' })).toBe(false)
    expect(
      isOrgPrivatized({
        mindmate_agent_name: '小助手',
        mindmate_agent_avatar_url: '/static/org_mindmate_avatars/1/avatar.png',
        dify_api_base_url: 'https://dify.example.com/v1',
        dify_api_key_masked: 'app-****',
      })
    ).toBe(true)
    expect(isOrgPrivatized({ mindmate_agent_name: '   ', dify_api_key_masked: null })).toBe(false)
  })
})

describe('buildPrivatizedColumnFilters', () => {
  it('returns string filter values for Element Plus table columns', () => {
    expect(buildPrivatizedColumnFilters('Yes', 'No')).toEqual([
      { text: 'Yes', value: 'yes' },
      { text: 'No', value: 'no' },
    ])
  })
})

describe('filterOrgByPrivatized', () => {
  it('matches privatized and non-privatized rows', () => {
    const privatizedRow = { is_privatized: true }
    const publicRow = { is_privatized: false }

    expect(filterOrgByPrivatized('yes', privatizedRow)).toBe(true)
    expect(filterOrgByPrivatized('yes', publicRow)).toBe(false)
    expect(filterOrgByPrivatized('no', publicRow)).toBe(true)
    expect(filterOrgByPrivatized('no', privatizedRow)).toBe(false)
    expect(filterOrgByPrivatized('unknown', privatizedRow)).toBe(true)
  })
})
