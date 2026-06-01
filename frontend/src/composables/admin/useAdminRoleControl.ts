/**
 * Role control tab — load, grant, and revoke members per platform role.
 */
import { computed, ref, watch } from 'vue'

import { useDebounceFn } from '@vueuse/core'

import { ElMessageBox } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import type { RoleControlTab } from '@/composables/admin/adminRoleControlNav'
import {
  useAddAdminOrganizationManager,
  useAdminAdmins,
  useAdminManagers,
  useAdminPlatformRoleMembers,
  useAdminUsers,
  useRemoveAdminOrganizationManager,
  useUpdateAdminUserRole,
} from '@/composables/queries'
import type { UserRole } from '@/types'
import { normalizeUserRole, userRoleLabel } from '@/utils/userRoleDisplay'

export interface AdminUser {
  id: number
  phone: string
  name: string | null
  role: string
  source: string
  created_at: string | null
}

export interface CandidateUser {
  id: number
  phone: string
  name: string | null
  role: string
  organization_id?: number | null
  organization_code?: string | null
  organization_name?: string | null
}

export interface EnvAdmin {
  phone: string
  user_id?: number | null
  name: string | null
}

export interface ManagerUser {
  id: number
  phone: string
  name: string | null
  organization_id: number | null
  organization_code: string | null
  organization_name: string | null
  created_at: string | null
}

export interface PlatformRoleMember {
  id: number
  phone: string
  name: string | null
  role: string
  source: 'database'
  created_at: string | null
}

export type RoleMemberRow =
  | (AdminUser & { source: 'database' | 'env' })
  | PlatformRoleMember
  | ManagerUser

export function useAdminRoleControl() {
  const { t } = useLanguage()
  const notify = useNotifications()

  const activeTab = ref<RoleControlTab>('superadmin')
  const revokingId = ref<number | null>(null)

  const addModalVisible = ref(false)
  const addSearchQuery = ref('')
  const addSearchResults = ref<CandidateUser[]>([])
  const addSearchLoading = ref(false)
  const addSearchHasRun = ref(false)
  const addGrantingId = ref<number | null>(null)

  const adminsQuery = useAdminAdmins({
    enabled: computed(() => activeTab.value === 'superadmin'),
  })
  const platformBdQuery = useAdminPlatformRoleMembers(
    computed(() => 'platform_bd'),
    { enabled: computed(() => activeTab.value === 'platform_bd') }
  )
  const expertQuery = useAdminPlatformRoleMembers(
    computed(() => 'expert'),
    { enabled: computed(() => activeTab.value === 'expert') }
  )
  const managersQuery = useAdminManagers({
    enabled: computed(() => activeTab.value === 'school_admin'),
  })

  const userSearchParams = computed(() => ({
    page: 1,
    page_size: 20,
    search: addSearchQuery.value.trim(),
  }))
  const userSearchEnabled = computed(() => addSearchQuery.value.trim().length >= 2)
  const userSearchQuery = useAdminUsers(userSearchParams, {
    enabled: userSearchEnabled,
  })

  const addManagerMutation = useAddAdminOrganizationManager()
  const removeManagerMutation = useRemoveAdminOrganizationManager()
  const updateRoleMutation = useUpdateAdminUserRole()

  const admins = computed(() => adminsQuery.data.value?.admins ?? [])
  const envAdmins = computed(() => adminsQuery.data.value?.env_admins ?? [])
  const platformBdMembers = computed(() => platformBdQuery.data.value ?? [])
  const expertMembers = computed(() => expertQuery.data.value ?? [])
  const managers = computed(() => managersQuery.data.value ?? [])

  const isLoading = computed(() => {
    switch (activeTab.value) {
      case 'superadmin':
        return adminsQuery.isFetching.value
      case 'platform_bd':
        return platformBdQuery.isFetching.value
      case 'expert':
        return expertQuery.isFetching.value
      case 'school_admin':
        return managersQuery.isFetching.value
      default:
        return false
    }
  })

  function maskPhone(phone: string): string {
    if (phone.length === 11) {
      return phone.slice(0, 3) + '****' + phone.slice(-4)
    }
    return phone
  }

  function roleLabel(role: string): string {
    return userRoleLabel(t, role)
  }

  function tabLabel(role: RoleControlTab): string {
    return roleLabel(role)
  }

  const superadminRows = computed((): RoleMemberRow[] => {
    const dbRows = admins.value.map((row) => ({
      ...row,
      source: 'database' as const,
    }))
    const envRows = envAdmins.value.map((row) => ({
      id: 0,
      phone: maskPhone(row.phone),
      name: row.name,
      role: 'superadmin',
      source: 'env' as const,
      created_at: null,
    }))
    return [...dbRows, ...envRows]
  })

  const activeRows = computed((): RoleMemberRow[] => {
    switch (activeTab.value) {
      case 'superadmin':
        return superadminRows.value
      case 'platform_bd':
        return platformBdMembers.value
      case 'expert':
        return expertMembers.value
      case 'school_admin':
        return managers.value
      default:
        return []
    }
  })

  const activeTabDescKey = computed(() => roleTabDescKey(activeTab.value))

  function roleTabDescKey(role: RoleControlTab): string {
    const keys: Record<RoleControlTab, string> = {
      superadmin: 'admin.roleControlDesc',
      platform_bd: 'admin.roleControlDescPlatformBd',
      expert: 'admin.roleControlDescExpert',
      school_admin: 'admin.roleControlDescManagers',
    }
    return keys[role]
  }

  async function loadActiveTab(): Promise<void> {
    try {
      switch (activeTab.value) {
        case 'superadmin':
          await adminsQuery.refetch()
          break
        case 'platform_bd':
          await platformBdQuery.refetch()
          break
        case 'expert':
          await expertQuery.refetch()
          break
        case 'school_admin':
          await managersQuery.refetch()
          break
        default:
          break
      }
    } catch {
      notify.error(t('admin.roleMembersLoadFailed'))
    }
  }

  function existingMemberIds(): Set<number> {
    switch (activeTab.value) {
      case 'superadmin':
        return new Set(admins.value.map((row) => row.id))
      case 'platform_bd':
        return new Set(platformBdMembers.value.map((row) => row.id))
      case 'expert':
        return new Set(expertMembers.value.map((row) => row.id))
      case 'school_admin':
        return new Set(managers.value.map((row) => row.id))
      default:
        return new Set()
    }
  }

  async function searchUsersToAdd(): Promise<void> {
    const q = addSearchQuery.value.trim()
    if (!q || q.length < 2) {
      addSearchResults.value = []
      addSearchHasRun.value = false
      return
    }
    addSearchLoading.value = true
    try {
      const result = await userSearchQuery.refetch()
      const users = (result.data?.users ?? []) as unknown as CandidateUser[]
      const memberIds = existingMemberIds()
      const targetRole = activeTab.value
      addSearchResults.value = users.filter((user) => {
        if (memberIds.has(user.id)) {
          return false
        }
        if (normalizeUserRole(user.role) === targetRole) {
          return false
        }
        if (targetRole === 'school_admin' && user.organization_id == null) {
          return false
        }
        return true
      })
    } catch {
      addSearchResults.value = []
      notify.error(t('admin.userSearchFailed'))
    } finally {
      addSearchLoading.value = false
      addSearchHasRun.value = true
    }
  }

  const debouncedSearchUsersToAdd = useDebounceFn(searchUsersToAdd, 400)

  watch(addSearchQuery, (val) => {
    const q = val.trim()
    if (q.length >= 2) {
      debouncedSearchUsersToAdd()
    } else {
      addSearchResults.value = []
      addSearchHasRun.value = false
    }
  })

  watch(activeTab, () => {
    addModalVisible.value = false
    void loadActiveTab()
  })

  function openAddModal(): void {
    addModalVisible.value = true
    addSearchQuery.value = ''
    addSearchResults.value = []
    addSearchHasRun.value = false
  }

  async function grantSchoolManager(user: CandidateUser): Promise<boolean> {
    const orgId = user.organization_id
    if (orgId == null) {
      notify.error(t('admin.schoolManagerGrantRequiresOrg'))
      return false
    }
    try {
      await addManagerMutation.mutateAsync({ orgId, userId: user.id })
      notify.success(t('admin.roleAssignSuccess'))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : t('admin.trendChartErrors.setManagerFailed')
      notify.error(message)
      return false
    }
  }

  async function removeSchoolManager(userId: number, orgId: number): Promise<boolean> {
    try {
      await removeManagerMutation.mutateAsync({ orgId, userId })
      notify.success(t('admin.managerRoleRemoved'))
      return true
    } catch (err) {
      const message =
        err instanceof Error ? err.message : t('admin.trendChartErrors.removeManagerFailed')
      notify.error(message)
      return false
    }
  }

  async function updateUserRole(userId: number, role: UserRole): Promise<boolean> {
    try {
      await updateRoleMutation.mutateAsync({ userId, role })
      notify.success(t('admin.roleAssignSuccess'))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : t('admin.roleAssignFailed')
      notify.error(message)
      return false
    }
  }

  async function grantActiveRole(user: CandidateUser): Promise<void> {
    addGrantingId.value = user.id
    try {
      const ok =
        activeTab.value === 'school_admin'
          ? await grantSchoolManager(user)
          : await updateUserRole(user.id, activeTab.value)
      if (ok) {
        addModalVisible.value = false
        await loadActiveTab()
      }
    } finally {
      addGrantingId.value = null
    }
  }

  async function revokeMember(row: RoleMemberRow): Promise<void> {
    if ('source' in row && row.source === 'env') {
      return
    }

    const displayName = row.name || row.phone
    const roleName = roleLabel(activeTab.value)
    try {
      await ElMessageBox.confirm(
        `${t('admin.revokeRoleConfirm')} ${displayName} (${roleName})?`,
        t('admin.revokeRole'),
        {
          type: 'warning',
          confirmButtonText: t('admin.confirm'),
          cancelButtonText: t('admin.cancel'),
        }
      )
    } catch {
      return
    }

    revokingId.value = row.id
    try {
      let ok = false
      if (
        activeTab.value === 'school_admin' &&
        'organization_id' in row &&
        row.organization_id != null
      ) {
        ok = await removeSchoolManager(row.id, row.organization_id)
      } else {
        ok = await updateUserRole(row.id, 'teacher')
      }
      if (ok) {
        await loadActiveTab()
      }
    } catch {
      notify.error(t('admin.roleAssignFailed'))
    } finally {
      revokingId.value = null
    }
  }

  function isEnvRow(row: RoleMemberRow): boolean {
    return 'source' in row && row.source === 'env'
  }

  return {
    activeTab,
    activeRows,
    activeTabDescKey,
    addGrantingId,
    addModalVisible,
    addSearchHasRun,
    addSearchLoading,
    addSearchQuery,
    addSearchResults,
    grantActiveRole,
    isEnvRow,
    isLoading,
    loadActiveTab,
    openAddModal,
    revokeMember,
    revokingId,
    roleLabel,
    roleTabDescKey,
    searchUsersToAdd,
    tabLabel,
  }
}
