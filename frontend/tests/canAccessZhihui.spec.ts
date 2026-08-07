import { describe, expect, it } from 'vitest'

import {
  canAccessZhihui,
  type AdminCapability,
} from '@/utils/adminCapabilities'

describe('canAccessZhihui', () => {
  it('allows feature.zhihui capability', () => {
    const caps: AdminCapability[] = ['panel.access', 'feature.zhihui']
    expect(canAccessZhihui(caps)).toBe(true)
  })

  it('denies school-manager style caps without feature.zhihui', () => {
    const caps: AdminCapability[] = [
      'panel.access',
      'tab.school_dashboard.view',
      'tab.users.view',
      'tab.users.edit',
      'scope.org',
    ]
    expect(canAccessZhihui(caps)).toBe(false)
  })

  it('denies empty capabilities', () => {
    expect(canAccessZhihui([])).toBe(false)
  })
})
