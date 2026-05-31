/**
 * Registry so AdminRolesTab exposes add/refresh actions to AdminPage header.
 */
import type { Ref } from 'vue'
import { shallowRef } from 'vue'

import type { UserRole } from '@/types'

export type RoleControlTab = Extract<UserRole, 'superadmin' | 'platform_bd' | 'expert' | 'school_admin'>

export interface AdminRolesHeaderToolbarModel {
  activeRoleTab: Ref<RoleControlTab>
  canEdit: Ref<boolean>
  isRefreshing: Ref<boolean>
  refresh: () => void | Promise<void>
  openAddModal: () => void
}

const toolbarModel = shallowRef<AdminRolesHeaderToolbarModel | null>(null)

export function registerAdminRolesHeaderToolbar(model: AdminRolesHeaderToolbarModel): void {
  toolbarModel.value = model
}

export function unregisterAdminRolesHeaderToolbar(): void {
  toolbarModel.value = null
}

export function useAdminRolesHeaderToolbarModel() {
  return toolbarModel
}

export const ROLE_CONTROL_TABS: readonly RoleControlTab[] = [
  'superadmin',
  'platform_bd',
  'expert',
  'school_admin',
]

export function isRoleControlTab(value: unknown): value is RoleControlTab {
  return typeof value === 'string' && ROLE_CONTROL_TABS.includes(value as RoleControlTab)
}
