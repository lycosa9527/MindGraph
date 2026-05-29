/**
 * Data center sub-views (sidebar + AdminDataCenterTab).
 */

export type DataCenterView = 'operations' | 'usage' | 'school_dashboard'

export const DATA_CENTER_VIEWS: ReadonlyArray<{
  name: DataCenterView
  labelKey: string
}> = [
  { name: 'operations', labelKey: 'admin.dataCenterOperations' },
  { name: 'usage', labelKey: 'admin.dataCenterUsage' },
  { name: 'school_dashboard', labelKey: 'admin.schoolDashboard' },
]

export function isDataCenterView(value: string | null | undefined): value is DataCenterView {
  return DATA_CENTER_VIEWS.some((view) => view.name === value)
}

export function defaultDataCenterView(hasGlobalScope: boolean): DataCenterView {
  return hasGlobalScope ? 'operations' : 'school_dashboard'
}
