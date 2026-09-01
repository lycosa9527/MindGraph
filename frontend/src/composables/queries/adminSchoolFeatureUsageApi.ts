/**
 * School-dashboard feature-usage analytics API.
 */
import { adminFetchJson } from './adminApi'

export type SchoolFeatureUsageCapacity = 'idle' | 'tense' | 'ample' | 'normal'

export interface SchoolFeatureUsageSeriesPoint {
  date: string
  value: number
}

export interface SchoolFeatureUsageModule {
  key: string
  visits: number
  uses: number
  ops_per_visitor: number
  completed: number
  pass_rate: number
  fail_rate: number | null
  avg_duration_seconds: number | null
  capacity: SchoolFeatureUsageCapacity
  monthly_uses: SchoolFeatureUsageSeriesPoint[]
}

export interface SchoolFeatureUsageRanked {
  key: string
  visits: number
  uses: number
  usage_rate: number | null
}

export interface SchoolFeatureUsageBottleneckSlots {
  lowest_pass_keys: string[]
  tense_keys: string[]
  slow_keys: string[]
  uniformly_high: boolean
  no_bottleneck: boolean
}

export interface SchoolFeatureUsageConclusionSlots {
  top_keys: string[]
  idle_keys: string[]
  concentrated: boolean
}

export interface SchoolFeatureUsageJudgement {
  top5: SchoolFeatureUsageRanked[]
  high: string[]
  low: string[]
  idle: string[]
  bottleneck_slots: SchoolFeatureUsageBottleneckSlots
  conclusion_slots: SchoolFeatureUsageConclusionSlots
}

export interface SchoolFeatureUsageResponse {
  year: number
  min_year: number
  generated_at: string
  enrolled: number
  modules: SchoolFeatureUsageModule[]
  judgement: SchoolFeatureUsageJudgement
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

export async function fetchAdminSchoolFeatureUsage(
  organizationId: number,
  year: number,
  signal?: AbortSignal
): Promise<SchoolFeatureUsageResponse> {
  return adminFetchJson(
    `/api/auth/admin/stats/school/feature-usage${buildQuery({
      organization_id: organizationId,
      year,
    })}`,
    { signal }
  )
}
