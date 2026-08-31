/**
 * School-dashboard user-activity analytics API.
 */
import { adminFetchJson } from './adminApi'

export interface SchoolActivitySeriesPoint {
  date: string
  value: number
}

export interface SchoolActivityHourPoint {
  hour: number
  value: number
}

export interface SchoolActivityBucketPoint {
  label: string
  value: number
}

export interface SchoolUserActivityTotals {
  cumulative_registered: number
  year_new_users: number
  churn_available: boolean
  enrolled_today: number
  cumulative_series: SchoolActivitySeriesPoint[]
  year_new_series: SchoolActivitySeriesPoint[]
  enrolled_series: SchoolActivitySeriesPoint[]
}

export interface SchoolUserActivityActive {
  daily_active: SchoolActivitySeriesPoint[]
  monthly_active: SchoolActivitySeriesPoint[]
  quarterly_active: SchoolActivitySeriesPoint[]
  avg_daily_active: number
  avg_monthly_active: number
}

export interface SchoolUserActivityFrequency {
  login_count_buckets: SchoolActivityBucketPoint[]
  high_freq_count: number
  high_freq_share: number
  low_freq_count: number
  low_freq_share: number
  hour_of_day: SchoolActivityHourPoint[]
}

export interface SchoolUserActivityResponse {
  year: number
  min_year: number
  generated_at: string
  totals: SchoolUserActivityTotals
  activity: SchoolUserActivityActive
  frequency: SchoolUserActivityFrequency
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) {
      continue
    }
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminSchoolUserActivity(
  organizationId: number,
  year: number,
  signal?: AbortSignal
): Promise<SchoolUserActivityResponse> {
  return adminFetchJson(
    `/api/auth/admin/stats/school/user-activity${buildQuery({
      organization_id: organizationId,
      year,
    })}`,
    { signal }
  )
}
