/**
 * Mobile organization management — list schools and show each invite in place.
 */
import { computed, nextTick, ref } from 'vue'

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
import { type MobileOrganizationRow, mergeCreatedMobileOrg } from '@/utils/mobileOrganizations'

export interface MobileOrgRow {
  id: number
  name: string
  invitationCode: string
  inviteLink: string
  userCount: number
}

interface CreatedOrganizationPayload {
  id?: number
  invitation_code?: string
}

interface CreatedOrgDraft {
  id: number
  name: string
  invitationCode: string
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

function withInviteLink(row: Omit<MobileOrgRow, 'inviteLink'>, siteUrl: string): MobileOrgRow {
  return {
    ...row,
    inviteLink: buildOrganizationInviteLink(siteUrl, row.invitationCode),
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
  const createdDraft = ref<CreatedOrgDraft | null>(null)

  const organizations = computed((): MobileOrgRow[] => {
    const rows = orgsQuery.data.value
    const listed = Array.isArray(rows) ? rows.map((row) => toOrgRow(row, publicSiteUrl.value)) : []
    const siteUrl = publicSiteUrl.value
    return mergeCreatedMobileOrg(listed, createdDraft.value).map((row) =>
      withInviteLink(row, siteUrl)
    )
  })

  const isLoading = computed(() => orgsQuery.isFetching.value && organizations.value.length === 0)

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

  function toggleExpanded(orgId: number): void {
    expandedId.value = expandedId.value === orgId ? null : orgId
  }

  async function scrollOrgIntoView(orgId: number): Promise<void> {
    await nextTick()
    document.getElementById(`mobile-org-${orgId}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
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
      })) as CreatedOrganizationPayload
      const createdId = Number(data.id)
      orgName.value = ''
      notify.success(t('notification.saved'))
      if (!Number.isFinite(createdId) || createdId <= 0) {
        return
      }
      createdDraft.value = {
        id: createdId,
        name,
        invitationCode: String(data.invitation_code ?? '').trim(),
      }
      expandedId.value = createdId
      await orgsQuery.refetch().catch(() => undefined)
      await scrollOrgIntoView(createdId)
    } catch (err) {
      const message = err instanceof Error ? err.message : t('admin.organizationCreateFailed')
      notify.error(message)
    } finally {
      isSubmitting.value = false
    }
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
