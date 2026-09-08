import { describe, expect, it } from 'vitest'

import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'

const PREVIEW = [5]

describe('userCanAccessWorkshopChat', () => {
  it('allows superadmin regardless of org', () => {
    expect(userCanAccessWorkshopChat(true, undefined, '1', PREVIEW, undefined)).toBe(true)
  })

  it('allows org 5 members via preview list', () => {
    expect(userCanAccessWorkshopChat(false, '5', '10', PREVIEW, undefined)).toBe(true)
  })

  it('denies other orgs even when school admin would previously pass', () => {
    expect(userCanAccessWorkshopChat(false, '7', '10', PREVIEW, undefined)).toBe(false)
  })

  it('denies unrestricted DB grants outside the preview list', () => {
    expect(
      userCanAccessWorkshopChat(false, '7', '10', PREVIEW, {
        restrict: false,
        organization_ids: [],
        user_ids: [],
      })
    ).toBe(false)
    expect(
      userCanAccessWorkshopChat(false, '5', '10', PREVIEW, {
        restrict: false,
        organization_ids: [],
        user_ids: [],
      })
    ).toBe(true)
  })

  it('requires a matching grant when the DB row is restricted', () => {
    const restricted = { restrict: true, organization_ids: [5], user_ids: [] }
    expect(userCanAccessWorkshopChat(false, '5', '10', PREVIEW, restricted)).toBe(true)
    expect(userCanAccessWorkshopChat(false, '5', '10', PREVIEW, {
      restrict: true,
      organization_ids: [9],
      user_ids: [],
    })).toBe(false)
  })
})
