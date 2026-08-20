/**
 * Mobile organization management — list invited orgs and create on the go.
 */
import { computed, ref } from 'vue'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useCreateAdminOrganization, useMobileOrganizations } from '@/composables/queries'
import { useAuthStore } from '@/stores'
import { canSeeMobileOrgManagement } from '@/utils/adminCapabilities'
import {
  buildOrganizationInviteLink,
  defaultOrganizationExpiresAtDate,
  sanitizeOrganizationName,
  uniqueSchoolCodeFromName,
} from '@/utils/invitationCode'
import type { MobileOrganizationRow } from '@/utils/mobileOrganizations'

export interface MobileOrgRow {
  id: number
  name: string
  invitationCode: string
  inviteLink: string
  userCount: number
}

function toOrgRow(row: MobileOrganizationRow, siteUrl: string): MobileOrgRow {
  const invitationCode = String(row.invitation_code ?? '').trim()
  return {
    id: Number(row.id),
    name: String(row.name ?? ''),
    invitationCode,
    inviteLink: buildOrganizationInviteLink(siteUrl, invitationCode),
    userCount: Number(row.user_count ?? 0),
  }
}

export function useMobileOrgManagement() {
  const { t } = useLanguage()
  const notify = useNotifications()
  const { publicSiteUrl } = usePublicSiteUrl()
  const authStore = useAuthStore()
  const createOrganization = useCreateAdminOrganization()

  const canManage = computed(() =>
    canSeeMobileOrgManagement(authStore.adminCapabilitiesPayload, authStore.adminCapabilitiesLoaded)
  )

  const orgsQuery = useMobileOrganizations({
    enabled: canManage,
  })

  const orgName = ref('')
  const isSubmitting = ref(false)
  const expandedId = ref<number | null>(null)

  const organizations = computed((): MobileOrgRow[] => {
    const rows = orgsQuery.data.value
    if (!Array.isArray(rows)) {
      return []
    }
    return rows.map((row) => toOrgRow(row, publicSiteUrl.value))
  })

  const isLoading = computed(() => orgsQuery.isFetching.value)

  async function copyText(text: string): Promise<void> {
    const value = text.trim()
    if (!value) {
      return
    }
    try {
      await navigator.clipboard.writeText(value)
      notify.success(t('notification.copied'))
    } catch {
      notify.error(t('notification.copyFailed'))
    }
  }

  async function submitCreate(): Promise<void> {
    const name = sanitizeOrganizationName(orgName.value)
    if (!name) {
      notify.error(t('admin.organizationNameRequired'))
      return
    }

    isSubmitting.value = true
    try {
      const data = (await createOrganization.mutateAsync({
        name,
        code: uniqueSchoolCodeFromName(name),
        expires_at: `${defaultOrganizationExpiresAtDate()}T23:59:59+08:00`,
      })) as { id?: number }
      orgName.value = ''
      notify.success(t('notification.saved'))
      await orgsQuery.refetch()
      if (data.id != null) {
        expandedId.value = Number(data.id)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('admin.organizationCreateFailed')
      notify.error(message)
    } finally {
      isSubmitting.value = false
    }
  }

  function toggleExpanded(orgId: number): void {
    expandedId.value = expandedId.value === orgId ? null : orgId
  }

  return {
    orgName,
    isSubmitting,
    isLoading,
    organizations,
    expandedId,
    submitCreate,
    toggleExpanded,
    copyText,
  }
}
