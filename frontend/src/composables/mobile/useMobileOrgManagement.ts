/**
 * Mobile organization management — list schools and open a school's chart card.
 */
import { computed, ref } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  ADMIN_STALE_MS,
  adminKeys,
  fetchAdminOrganizations,
  useCreateAdminOrganization,
  useMobileOrganizations,
} from '@/composables/queries'
import { useAuthStore } from '@/stores'
import { type SchoolDiagramCard, schoolDiagramCardFromRow } from '@/utils/admin/schoolDiagramCard'
import { canSeeMobileOrgManagement } from '@/utils/adminCapabilities'
import {
  defaultOrganizationExpiresAtDate,
  sanitizeOrganizationName,
  uniqueSchoolCodeFromName,
} from '@/utils/invitationCode'
import type { MobileOrganizationRow } from '@/utils/mobileOrganizations'

export interface MobileOrgRow {
  id: number
  name: string
  invitationCode: string
  userCount: number
}

interface CreatedOrganizationPayload {
  id?: number
  name?: string
  invitation_code?: string
}

function toOrgRow(row: MobileOrganizationRow): MobileOrgRow {
  return {
    id: Number(row.id),
    name: String(row.name ?? ''),
    invitationCode: String(row.invitation_code ?? '').trim(),
    userCount: Number(row.user_count ?? 0),
  }
}

export function useMobileOrgManagement() {
  const { t } = useLanguage()
  const notify = useNotifications()
  const queryClient = useQueryClient()
  const authStore = useAuthStore()
  const { can } = useAdminAccess()
  const createOrganization = useCreateAdminOrganization()

  const canManage = computed(() =>
    canSeeMobileOrgManagement(authStore.adminCapabilitiesPayload, authStore.adminCapabilitiesLoaded)
  )

  const orgsQuery = useMobileOrganizations({
    enabled: canManage,
  })

  const orgName = ref('')
  const isSubmitting = ref(false)
  const openingId = ref<number | null>(null)
  const diagramVisible = ref(false)
  const diagramSchool = ref<SchoolDiagramCard | null>(null)
  const diagramDetailReady = ref(false)

  const organizations = computed((): MobileOrgRow[] => {
    const rows = orgsQuery.data.value
    if (!Array.isArray(rows)) {
      return []
    }
    return rows.map((row) => toOrgRow(row)).sort((left, right) => right.id - left.id)
  })

  const canEditSchool = computed(() => can('tab.organizations.edit'))

  const schoolDialogMode = computed((): 'manage' | 'insights' => {
    if (!diagramDetailReady.value) {
      return 'insights'
    }
    return can('scope.invited_orgs') && !can('scope.global') ? 'insights' : 'manage'
  })

  const diagramReadOnly = computed(() => !diagramDetailReady.value || !canEditSchool.value)

  const isLoading = computed(() => orgsQuery.isFetching.value && organizations.value.length === 0)

  function invitationCodeFor(orgId: number, explicitCode = ''): string {
    const provided = explicitCode.trim()
    if (provided) {
      return provided
    }
    return organizations.value.find((org) => org.id === orgId)?.invitationCode ?? ''
  }

  async function loadAdminOrganizations(): Promise<Record<string, unknown>[]> {
    const data = await queryClient.fetchQuery({
      queryKey: adminKeys.organizations(),
      queryFn: fetchAdminOrganizations,
      staleTime: ADMIN_STALE_MS.organizations,
    })
    if (!Array.isArray(data)) {
      return []
    }
    return data.map((item) => item as unknown as Record<string, unknown>)
  }

  async function openSchool(orgId: number, invitationCode = '', force = false): Promise<void> {
    if (!force && openingId.value != null) {
      return
    }
    openingId.value = orgId
    try {
      const rows = await loadAdminOrganizations()
      const listed = rows.find((item) => Number(item.id) === orgId)
      const mobile = organizations.value.find((org) => org.id === orgId)
      const row = listed ?? {
        id: orgId,
        name: mobile?.name ?? '',
        user_count: mobile?.userCount ?? 0,
      }
      diagramDetailReady.value = listed != null
      diagramSchool.value = schoolDiagramCardFromRow(row, {
        invitationCode: invitationCodeFor(orgId, invitationCode),
        initialTab: 'usage',
      })
      diagramVisible.value = true
    } catch {
      notify.error(t('admin.schoolsLoadError'))
    } finally {
      openingId.value = null
    }
  }

  async function refreshOpenedSchool(): Promise<void> {
    await orgsQuery.refetch()
    await queryClient.invalidateQueries({ queryKey: adminKeys.organizations() })
    const current = diagramSchool.value
    if (current?.id == null) {
      return
    }
    try {
      const rows = await loadAdminOrganizations()
      const listed = rows.find((item) => Number(item.id) === current.id)
      if (!listed) {
        return
      }
      diagramDetailReady.value = true
      diagramSchool.value = schoolDiagramCardFromRow(listed, {
        invitationCode: current.invitationCode,
        initialTab: current.initial_tab,
        initialTrendPeriod: current.initial_trend_period,
      })
    } catch {
      notify.error(t('admin.schoolsLoadError'))
    }
  }

  async function submitCreate(): Promise<void> {
    const name = sanitizeOrganizationName(orgName.value)
    if (!name) {
      notify.error(t('admin.organizationNameRequired'))
      return
    }

    isSubmitting.value = true
    let createdId: number | undefined
    let invitationCode: string | undefined
    try {
      const data = (await createOrganization.mutateAsync({
        name,
        code: uniqueSchoolCodeFromName(name),
        expires_at: `${defaultOrganizationExpiresAtDate()}T23:59:59+08:00`,
      })) as CreatedOrganizationPayload
      createdId = Number(data.id)
      invitationCode = String(data.invitation_code ?? '')
      orgName.value = ''
      notify.success(t('notification.saved'))
    } catch (err) {
      const message = err instanceof Error ? err.message : t('admin.organizationCreateFailed')
      notify.error(message)
      return
    } finally {
      isSubmitting.value = false
    }

    if (createdId == null || !Number.isFinite(createdId) || createdId <= 0) {
      return
    }
    await orgsQuery.refetch().catch(() => undefined)
    await openSchool(createdId, invitationCode ?? '', true)
  }

  return {
    orgName,
    isSubmitting,
    isLoading,
    openingId,
    organizations,
    diagramVisible,
    diagramSchool,
    schoolDialogMode,
    diagramReadOnly,
    submitCreate,
    openSchool,
    refreshOpenedSchool,
  }
}
