/**
 * Shared types and group constants for teacher usage analytics.
 */

export interface GroupDefinition {
  id: string
}

export const TOP_LEVEL_GROUPS: GroupDefinition[] = [{ id: 'unused' }, { id: 'continuous' }]

export const SUB_GROUPS: GroupDefinition[] = [
  { id: 'rejection' },
  { id: 'stopped' },
  { id: 'intermittent' },
]

export const GROUPS = [...TOP_LEVEL_GROUPS, ...SUB_GROUPS]

export interface Teacher {
  id: number
  username: string
  diagrams: number
  conceptGen: number
  relationshipLabels: number
  tokens: number
  lastActive: string
}

export interface GroupStats {
  count: number
  totalTokens: number
  teachers: Teacher[]
  weeklyTokens?: number[]
}

export type StatCardType =
  | 'total'
  | 'unused'
  | 'continuous'
  | 'rejection'
  | 'stopped'
  | 'intermittent'

export interface WeeklyDataPoint {
  date: string
  tokens: number
}

export interface ActivityTrendPoint {
  date: string
  editCount: number
  exportCount: number
  autocompleteCount: number
}

export interface UserDetailData {
  diagrams: number
  conceptGen: number
  relationshipLabels: number
  weeklyData: WeeklyDataPoint[]
  activityTrends: ActivityTrendPoint[]
  tokenStats: {
    today: { input_tokens: number; output_tokens: number; total_tokens: number }
    week: { input_tokens: number; output_tokens: number; total_tokens: number }
    month: { input_tokens: number; output_tokens: number; total_tokens: number }
    total: { input_tokens: number; output_tokens: number; total_tokens: number }
  }
}
