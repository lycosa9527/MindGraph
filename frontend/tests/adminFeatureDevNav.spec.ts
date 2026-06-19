import { describe, expect, it } from 'vitest'

import {
  type FeatureDevNavVisibilityOptions,
  resolveFeatureDevSubtab,
  visibleFeatureDevSubtabs,
} from '@/composables/admin/adminFeatureDevNav'

function options(
  overrides: Partial<FeatureDevNavVisibilityOptions> = {}
): FeatureDevNavVisibilityOptions {
  return {
    canViewSettingsSubtab: () => true,
    featureSmartResponse: false,
    featureTeacherUsage: false,
    featureKittyAgent: false,
    featureMindmateExport: false,
    ...overrides,
  }
}

describe('adminFeatureDevNav — mindmate_export', () => {
  it('hides the subtab when the feature flag is off', () => {
    expect(visibleFeatureDevSubtabs(options())).not.toContain('mindmate_export')
  })

  it('shows the subtab when flag on and capability granted', () => {
    const subtabs = visibleFeatureDevSubtabs(options({ featureMindmateExport: true }))
    expect(subtabs).toContain('mindmate_export')
  })

  it('hides the subtab when capability is missing even if flag is on', () => {
    const subtabs = visibleFeatureDevSubtabs(
      options({ featureMindmateExport: true, canViewSettingsSubtab: () => false })
    )
    expect(subtabs).not.toContain('mindmate_export')
  })

  it('resolves the requested subtab only when visible', () => {
    expect(
      resolveFeatureDevSubtab('mindmate_export', options({ featureMindmateExport: true }))
    ).toBe('mindmate_export')
    // not visible -> falls back to first visible (none here)
    expect(resolveFeatureDevSubtab('mindmate_export', options())).toBeNull()
  })
})
