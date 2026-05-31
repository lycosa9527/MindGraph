/**
 * Role control tab — load, grant, and revoke members per platform role.
 */
import { computed, ref, watch } from 'vue'

import { useDebounceFn } from '@vueuse/core'

import { ElMessageBox } from 'element-plus'

import { useLanguage, useNotifications } from '@/composables'
import type { RoleControlTab } from '@/composables/admin/useAdminRolesHeaderToolbar'
import type { UserRole } from '@/types'
import { apiRequest } from '@/utils/apiClient'
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
  const isLoading = ref(true)
  const admins = ref<AdminUser[]>([])
  const envAdmins = ref<EnvAdmin[]>([])
  const platformBdMembers = ref<PlatformRoleMember[]>([])
  const expertMembers = ref<PlatformRoleMember[]>([])
  const managers = ref<ManagerUser[]>([])
  const revokingId = ref<number | null>(null)

  const addModalVisible = ref(false)
  const addSearchQuery = ref('')
  const addSearchResults = ref<CandidateUser[]>([])
  const addSearchLoading = ref(false)
  const addSearchHasRun = ref(false)
  const addGrantingId = ref<number | null>(null)

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

  async function loadAdmins() {
    const res = await apiRequest('/api/auth/admin/admins')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.roleMembersLoadFailed'))
      admins.value = []
      envAdmins.value = []
      return false
    }
    const data = await res.json()
    admins.value = data.admins ?? []
    envAdmins.value = data.env_admins ?? []
    return true
  }

  async function loadPlatformMembers(role: 'platform_bd' | 'expert') {
    const targetRef = role === 'platform_bd' ? platformBdMembers : expertMembers
    targetRef.value = []
    const params = new URLSearchParams({ role })
    const res = await apiRequest(`/api/auth/admin/platform-role-members?${params}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.roleMembersLoadFailed'))
      targetRef.value = []
      return false
    }
    const data = await res.json()
    targetRef.value = (data.members ?? []) as PlatformRoleMember[]
    return true
  }

  async function loadManagers() {
    const res = await apiRequest('/api/auth/admin/managers')
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.roleMembersLoadFailed'))
      managers.value = []
      return false
    }
    const data = await res.json()
    managers.value = data.managers ?? []
    return true
  }

  async function loadActiveTab() {
    isLoading.value = true
    try {
      switch (activeTab.value) {
        case 'superadmin':
          await loadAdmins()
          break
        case 'platform_bd':
          await loadPlatformMembers('platform_bd')
          break
        case 'expert':
          await loadPlatformMembers('expert')
          break
        case 'school_admin':
          await loadManagers()
          break
        default:
          break
      }
    } catch {
      notify.error(t('admin.roleMembersLoadFailed'))
    } finally {
      isLoading.value = false
    }
  }

  async function searchUsers(query: string): Promise<CandidateUser[]> {
    const q = query.trim()
    if (!q || q.length < 2) {
      return []
    }
    const params = new URLSearchParams({
      page: '1',
      page_size: '20',
      search: q,
    })
    const res = await apiRequest(`/api/auth/admin/users?${params}`)
    if (!res.ok) {
      notify.error(t('admin.userSearchFailed'))
      return []
    }
    const data = await res.json()
    return (data.users ?? []) as CandidateUser[]
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

  async function searchUsersToAdd() {
    const q = addSearchQuery.value.trim()
    if (!q || q.length < 2) {
      addSearchResults.value = []
      addSearchHasRun.value = false
      return
    }
    addSearchLoading.value = true
    try {
      const users = await searchUsers(q)
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

  function openAddModal() {
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
    const res = await apiRequest(
      `/api/auth/admin/organizations/${orgId}/managers/${user.id}`,
      { method: 'PUT' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.setManagerFailed'))
      return false
    }
    const data = await res.json()
    notify.success((data.message as string) || t('admin.roleAssignSuccess'))
    return true
  }

  async function removeSchoolManager(userId: number, orgId: number): Promise<boolean> {
    const res = await apiRequest(
      `/api/auth/admin/organizations/${orgId}/managers/${userId}`,
      { method: 'DELETE' }
    )
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.trendChartErrors.removeManagerFailed'))
      return false
    }
    const data = await res.json()
    notify.success((data.message as string) || t('admin.managerRoleRemoved'))
    return true
  }

  async function updateUserRole(userId: number, role: UserRole): Promise<boolean> {
    const res = await apiRequest(`/api/auth/admin/users/${userId}/role?role=${role}`, {
      method: 'PUT',
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error((data.detail as string) || t('admin.roleAssignFailed'))
      return false
    }
    const data = await res.json()
    notify.success(data.message || t('admin.roleAssignSuccess'))
    return true
  }

  async function grantActiveRole(user: CandidateUser) {
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

  async function revokeMember(row: RoleMemberRow) {
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
