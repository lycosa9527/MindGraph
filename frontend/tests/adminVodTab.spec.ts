import { describe, expect, it } from 'vitest'

import { ADMIN_PANEL_TAB_CONFIG } from '@/composables/admin/adminPanelTabs'
import { formatVodDuration } from '@/composables/admin/vodMediaFormat'
import {
  fallbackCapabilitiesForRole,
  tabEditCapability,
  tabRequiresCapabilities,
} from '@/utils/adminCapabilities'

function isVodTabVisible(featureVod: boolean, capabilities: readonly string[]): boolean {
  return featureVod && tabRequiresCapabilities('vod').every((cap) => capabilities.includes(cap))
}

function canOpenVodUpload(capabilities: readonly string[]): boolean {
  const editCap = tabEditCapability('vod')
  return editCap != null && capabilities.includes(editCap)
}

describe('admin VOD library', () => {
  it('registers a top-level 云点播 tab', () => {
    const vod = ADMIN_PANEL_TAB_CONFIG.find((tab) => tab.name === 'vod')
    expect(vod?.labelKey).toBe('admin.vod.title')
  })

  it('shows the tab only when FEATURE_VOD and tab.vod.view are both on', () => {
    const school = fallbackCapabilitiesForRole('school_admin')
    const teacher = fallbackCapabilitiesForRole('teacher')
    expect(isVodTabVisible(true, school)).toBe(true)
    expect(isVodTabVisible(false, school)).toBe(false)
    expect(isVodTabVisible(true, teacher)).toBe(false)
  })

  it('gates the upload dialog on tab.vod.edit', () => {
    const school = fallbackCapabilitiesForRole('school_admin')
    const teacher = fallbackCapabilitiesForRole('teacher')
    expect(tabEditCapability('vod')).toBe('tab.vod.edit')
    expect(canOpenVodUpload(school)).toBe(true)
    expect(canOpenVodUpload(teacher)).toBe(false)
  })

  it('formats duration for cards and the table', () => {
    expect(formatVodDuration(null)).toBe('—')
    expect(formatVodDuration(1500)).toBe('0:01')
    expect(formatVodDuration(125000)).toBe('2:05')
    expect(formatVodDuration(3723000)).toBe('1:02:03')
  })
})
