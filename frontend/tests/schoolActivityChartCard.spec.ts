import { createApp, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import AdminSwissChartCard from '@/components/admin/swiss/AdminSwissChartCard.vue'
import SchoolActivityActiveSection from '@/components/school/SchoolActivityActiveSection.vue'
import SchoolActivityFrequencySection from '@/components/school/SchoolActivityFrequencySection.vue'
import SchoolActivityTotalsSection from '@/components/school/SchoolActivityTotalsSection.vue'
import { beijingCalendarYear, formatBeijingSnapshotTime } from '@/utils/schoolActivityAsOf'
import { fallbackCapabilitiesForRole } from '@/utils/adminCapabilities'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (params?.time) {
        return `As of ${params.time} (Beijing time)`
      }
      if (params?.count != null && params.share != null) {
        return `${params.count} (${params.share}%)`
      }
      return key
    },
  }),
}))

vi.mock('@/composables/school/useSchoolActivityChart', () => ({
  useSchoolActivityChart: () => undefined,
}))

describe('school activity chart cards', () => {
  it('formats generated_at as Beijing wall clock', () => {
    expect(formatBeijingSnapshotTime('2026-09-01T00:15:00+00:00')).toBe('2026-09-01 08:15')
  })

  it('reads the calendar year in Asia/Shanghai', () => {
    expect(beijingCalendarYear(new Date('2026-12-31T16:30:00.000Z'))).toBe(2027)
    expect(beijingCalendarYear(new Date('2026-12-31T15:30:00.000Z'))).toBe(2026)
  })

  it('renders the required timestamp on the churn empty card', () => {
    const host = document.createElement('div')
    const app = createApp({
      render() {
        return h(AdminSwissChartCard, {
          title: 'Churn',
          value: '—',
          timestamp: 'As of 2026-09-01 08:15 (Beijing time)',
          empty: true,
          emptyText: 'No historical data',
        })
      },
    })
    app.mount(host)
    const stamp = host.querySelector('[data-testid="school-activity-card-timestamp"]')
    expect(stamp?.textContent).toContain('2026-09-01 08:15')
    expect(host.textContent).toContain('No historical data')
    app.unmount()
  })

  it('hides the activity tab capability from school managers', () => {
    expect(fallbackCapabilitiesForRole('school_admin')).not.toContain(
      'tab.school_dashboard.activity.view'
    )
    expect(fallbackCapabilitiesForRole('superadmin')).toContain(
      'tab.school_dashboard.activity.view'
    )
  })

  it('renders twelve cards with a Beijing timestamp footer', () => {
    const stamp = 'As of 2026-09-01 08:15 (Beijing time)'
    const series = [{ date: '2026-01', value: 2 }]
    const host = document.createElement('div')
    const app = createApp({
      render() {
        return h('div', [
          h(SchoolActivityTotalsSection, {
            totals: {
              cumulative_registered: 2,
              year_new_users: 1,
              churn_available: false,
              enrolled_today: 2,
              cumulative_series: series,
              year_new_series: series,
              enrolled_series: series,
            },
            timestamp: stamp,
          }),
          h(SchoolActivityActiveSection, {
            activity: {
              daily_active: series,
              monthly_active: series,
              quarterly_active: [{ date: '2026-Q1', value: 1 }],
              avg_daily_active: 0.5,
              avg_monthly_active: 1.2,
            },
            timestamp: stamp,
          }),
          h(SchoolActivityFrequencySection, {
            frequency: {
              login_count_buckets: [{ label: '0', value: 1 }],
              high_freq_count: 0,
              high_freq_share: 0,
              low_freq_count: 1,
              low_freq_share: 100,
              hour_of_day: [{ hour: 8, value: 3 }],
            },
            timestamp: stamp,
          }),
        ])
      },
    })
    app.mount(host)
    const stamps = host.querySelectorAll('[data-testid="school-activity-card-timestamp"]')
    expect(stamps).toHaveLength(12)
    expect([...stamps].every((node) => node.textContent?.includes('2026-09-01 08:15'))).toBe(true)
    expect(host.textContent).toContain('admin.schoolActivity.churnEmpty')
    app.unmount()
  })
})
