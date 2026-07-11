/**
 * Admin panel shared state — route-synced tab context, org scope, active polls.
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import type { RoleControlTab } from '@/composables/admin/adminRoleControlNav'
import { eventBus } from '@/composables/core/useEventBus'

export type AdminPollKey = 'performance' | 'gewe_qr'

export interface AdminUsersToolbarState {
  searchQuery: string
  orgFilter: number | ''
  roleFilter: string
  showSchoolFilter: boolean
  showRoleFilter: boolean
  scopedOrgId: number | null
  hasResetFilters: boolean
}

export interface AdminRolesToolbarState {
  activeRoleTab: RoleControlTab
  canEdit: boolean
  isRefreshing: boolean
}

export interface AdminFeaturesToolbarState {
  saving: boolean
}

export const useAdminPanelStore = defineStore('adminPanel', () => {
  const selectedOrgId = ref<number | null>(null)
  const activeTab = ref<string>('data_center')
  const activeSubtab = ref<string | null>(null)
  const activeDataCenterView = ref<string | null>(null)
  const activePolls = ref<Set<AdminPollKey>>(new Set())
  const usersToolbar = ref<AdminUsersToolbarState | null>(null)
  const rolesToolbar = ref<AdminRolesToolbarState | null>(null)
  const featuresToolbar = ref<AdminFeaturesToolbarState | null>(null)

  function setSelectedOrgId(orgId: number | null): void {
    selectedOrgId.value = orgId
  }

  function registerPoll(key: AdminPollKey): void {
    if (activePolls.value.has(key)) {
      return
    }
    const next = new Set(activePolls.value)
    next.add(key)
    activePolls.value = next
  }

  function unregisterPoll(key: AdminPollKey): void {
    if (!activePolls.value.has(key)) {
      return
    }
    const next = new Set(activePolls.value)
    next.delete(key)
    activePolls.value = next
  }

  function isPollActive(key: AdminPollKey): boolean {
    return activePolls.value.has(key)
  }

  function invalidateDomain(domain: string): void {
    eventBus.emit('admin:refresh_requested', { domain })
  }

  function setUsersToolbar(state: AdminUsersToolbarState | null): void {
    usersToolbar.value = state
  }

  function patchUsersToolbar(partial: Partial<AdminUsersToolbarState>): void {
    if (!usersToolbar.value) {
      return
    }
    usersToolbar.value = { ...usersToolbar.value, ...partial }
  }

  function clearUsersToolbar(): void {
    usersToolbar.value = null
  }

  function setRolesToolbar(state: AdminRolesToolbarState | null): void {
    rolesToolbar.value = state
  }

  function patchRolesToolbar(partial: Partial<AdminRolesToolbarState>): void {
    if (!rolesToolbar.value) {
      return
    }
    rolesToolbar.value = { ...rolesToolbar.value, ...partial }
  }

  function clearRolesToolbar(): void {
    rolesToolbar.value = null
  }

  function setFeaturesToolbar(state: AdminFeaturesToolbarState | null): void {
    featuresToolbar.value = state
  }

  function patchFeaturesToolbar(partial: Partial<AdminFeaturesToolbarState>): void {
    if (!featuresToolbar.value) {
      return
    }
    featuresToolbar.value = { ...featuresToolbar.value, ...partial }
  }

  function clearFeaturesToolbar(): void {
    featuresToolbar.value = null
  }

  return {
    selectedOrgId,
    activeTab,
    activeSubtab,
    activeDataCenterView,
    activePolls,
    usersToolbar,
    rolesToolbar,
    featuresToolbar,
    setSelectedOrgId,
    registerPoll,
    unregisterPoll,
    isPollActive,
    invalidateDomain,
    setUsersToolbar,
    patchUsersToolbar,
    clearUsersToolbar,
    setRolesToolbar,
    patchRolesToolbar,
    clearRolesToolbar,
    setFeaturesToolbar,
    patchFeaturesToolbar,
    clearFeaturesToolbar,
  }
})
