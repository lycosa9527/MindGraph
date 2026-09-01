import { createApp, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import AdminSwissModuleStatCard from '@/components/admin/swiss/AdminSwissModuleStatCard.vue'
import SchoolFeatureUsageAccessSection from '@/components/school/SchoolFeatureUsageAccessSection.vue'
import SchoolFeatureUsageProcessSection from '@/components/school/SchoolFeatureUsageProcessSection.vue'
import { fallbackCapabilitiesForRole } from '@/utils/adminCapabilities'
import { formatBeijingSnapshotTime } from '@/utils/schoolActivityAsOf'
import type { SchoolFeatureUsageModule } from '@/composables/queries/adminSchoolFeatureUsageApi'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/composables/school/useSchoolActivityChart', () => ({
  useSchoolActivityChart: () => undefined,
}))

const idleMonthly = Array.from({ length: 12 }, (_, index) => ({
  date: `2026-${String(index + 1).padStart(2, '0')}`,
  value: 0,
}))

function moduleRow(key: string, uses: number): SchoolFeatureUsageModule {
  return {
    key,
    visits: uses > 0 ? 1 : 0,
    uses,
    ops_per_visitor: uses > 0 ? uses : 0,
    completed: uses,
    pass_rate: uses > 0 ? 100 : 0,
    fail_rate: uses > 0 ? 0 : null,
    avg_duration_seconds: uses > 0 ? 1.5 : null,
    capacity: uses > 0 ? 'ample' : 'idle',
    monthly_uses: idleMonthly.map((point, index) =>
      index === 0 ? { ...point, value: uses } : point
    ),
  }
}

describe('school feature usage cards', () => {
  it('formats generated_at as Beijing wall clock', () => {
    expect(formatBeijingSnapshotTime('2026-09-01T00:15:00+00:00')).toBe('2026-09-01 08:15')
  })

  it('hides the feature-usage tab capability from school managers', () => {
    expect(fallbackCapabilitiesForRole('school_admin')).not.toContain(
      'tab.school_dashboard.feature_usage.view'
    )
    expect(fallbackCapabilitiesForRole('superadmin')).toContain(
      'tab.school_dashboard.feature_usage.view'
    )
  })

  it('renders a timestamp on the module card', () => {
    const host = document.createElement('div')
    const app = createApp({
      render() {
        return h(AdminSwissModuleStatCard, {
          title: 'Diagram canvas',
          value: 3,
          timestamp: 'As of 2026-09-01 08:15 (Beijing time)',
          remark: 'Diagram generate, save, export, and canvas translate.',
        })
      },
    })
    app.mount(host)
    const stamp = host.querySelector('[data-testid="school-activity-card-timestamp"]')
    expect(stamp?.textContent).toContain('2026-09-01 08:15')
    app.unmount()
  })

  it('keeps idle modules after used ones', () => {
    const stamp = 'As of 2026-09-01 08:15 (Beijing time)'
    const host = document.createElement('div')
    const app = createApp({
      render() {
        return h(SchoolFeatureUsageAccessSection, {
          modules: [moduleRow('canvas', 4), moduleRow('askonce', 0)],
          timestamp: stamp,
        })
      },
    })
    app.mount(host)
    const cards = host.querySelectorAll('[data-testid="school-feature-usage-card"]')
    expect(cards.length).toBe(2)
    expect(cards[0]?.textContent).toContain('admin.schoolFeatureUsage.module.canvas')
    expect(cards[0]?.textContent).toContain('admin.schoolFeatureUsage.visits')
    expect(cards[1]?.textContent).toContain('admin.schoolFeatureUsage.module.askonce')
    expect(
      [...host.querySelectorAll('[data-testid="school-activity-card-timestamp"]')].every((node) =>
        node.textContent?.includes('2026-09-01 08:15')
      )
    ).toBe(true)
    app.unmount()
  })

  it('shows token duration and fail rate on process cards', () => {
    const stamp = 'As of 2026-09-01 08:15 (Beijing time)'
    const host = document.createElement('div')
    const app = createApp({
      render() {
        return h(SchoolFeatureUsageProcessSection, {
          modules: [moduleRow('canvas', 4), moduleRow('askonce', 0)],
          bottleneck: {
            lowest_pass_keys: [],
            tense_keys: [],
            slow_keys: ['canvas'],
            uniformly_high: true,
            no_bottleneck: false,
          },
          timestamp: stamp,
        })
      },
    })
    app.mount(host)
    const cards = host.querySelectorAll('[data-testid="school-feature-usage-card"]')
    expect(cards[0]?.textContent).toContain('admin.schoolFeatureUsage.completed')
    expect(cards[0]?.textContent).toContain('admin.schoolFeatureUsage.llmFailRate')
    expect(cards[0]?.textContent).toContain('admin.schoolFeatureUsage.llmDuration')
    expect(cards[0]?.textContent).not.toContain('admin.schoolFeatureUsage.durationEmpty')
    expect(cards[1]?.textContent).toContain('admin.schoolFeatureUsage.durationEmpty')
    expect(host.textContent).toContain('admin.schoolFeatureUsage.bottleneckSlow')
    app.unmount()
  })
})
