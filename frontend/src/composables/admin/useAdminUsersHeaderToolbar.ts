/**
 * Registry so user-list tabs can expose search controls to AdminPage header.
 */
import type { ComputedRef, Ref } from 'vue'
import { shallowRef } from 'vue'

export interface AdminUsersHeaderToolbarModel {
  searchQuery: Ref<string>
  /** Org context for breadcrumb when the list is school-scoped (e.g. SchoolDashboardUsersTab). */
  scopedOrgId?: ComputedRef<number> | Ref<number>
  orgFilter?: Ref<number | ''>
  /** When true, header shows school filter (options loaded via useAdminOrganizationsList). */
  showSchoolFilter?: boolean
  doSearch: () => void
  resetFilters?: () => void
  /** Fired when the school filter changes (select or clear). */
  onOrgFilterChange?: (value: number | '') => void
}

const toolbarModel = shallowRef<AdminUsersHeaderToolbarModel | null>(null)

export function registerAdminUsersHeaderToolbar(model: AdminUsersHeaderToolbarModel): void {
  toolbarModel.value = model
}

export function unregisterAdminUsersHeaderToolbar(): void {
  toolbarModel.value = null
}

export function useAdminUsersHeaderToolbarModel() {
  return toolbarModel
}
