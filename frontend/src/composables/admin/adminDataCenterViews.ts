/**
 * Data center sub-views (sidebar + AdminDataCenterTab).
 */

import type { AdminCapability } from '@/utils/adminCapabilities'

export type DataCenterView = 'operations' | 'usage' | 'school_dashboard'

export const DATA_CENTER_VIEWS: ReadonlyArray<{
  name: DataCenterView
  labelKey: string
}> = [
  { name: 'operations', labelKey: 'admin.dataCenterOperations' },
  { name: 'usage', labelKey: 'admin.dataCenterUsage' },
  { name: 'school_dashboard', labelKey: 'admin.schoolDashboard' },
]

const VIEW_CAPABILITY: Record<DataCenterView, AdminCapability[]> = {
  operations: ['tab.data_center.view'],
  usage: ['tab.data_center.view'],
  school_dashboard: ['tab.school_dashboard.view'],
}

export function isDataCenterView(value: string | null | undefined): value is DataCenterView {
  return DATA_CENTER_VIEWS.some((view) => view.name === value)
}

export function canViewDataCenterSubView(
  view: DataCenterView,
  caps: AdminCapability[]
): boolean {
  const required = VIEW_CAPABILITY[view]
  return required.every((cap) => caps.includes(cap))
}

export function visibleDataCenterViews(caps: AdminCapability[]): DataCenterView[] {
  return DATA_CENTER_VIEWS.filter((view) => canViewDataCenterSubView(view.name, caps)).map(
    (view) => view.name
  )
}

export function defaultDataCenterView(hasGlobalScope: boolean): DataCenterView {
  return hasGlobalScope ? 'operations' : 'school_dashboard'
}
