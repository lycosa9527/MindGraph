/**
 * School-scoped dashboard stats for the management panel data center.
 */
import { type Ref, computed } from 'vue'

import { useLanguage } from '@/composables'
import { useQueryErrorNotification } from '@/composables/admin/useQueryErrorNotification'
import { useAdminSchoolStats } from '@/composables/queries'
import {
  type SchoolDashboardQuotas,
  parseSchoolDashboardQuotas,
} from '@/composables/school/useSchoolDashboardQuotas'

export interface SchoolDashboardOrganization {
  id: number
  name: string
  code: string
  invitation_code: string
}

export interface SchoolDashboardTopUser {
  id: number
  name: string
  phone: string
  total_tokens: number
}

export interface SchoolDashboardStats {
  totalTokens: number
  organization: SchoolDashboardOrganization
  quotas: SchoolDashboardQuotas
}

function emptyOrganization(): SchoolDashboardOrganization {
  return { id: 0, name: '', code: '', invitation_code: '' }
}

function emptyQuotas(): SchoolDashboardQuotas {
  return parseSchoolDashboardQuotas(null)
}

function mapStats(data: Record<string, unknown> | undefined): SchoolDashboardStats {
  if (!data) {
    return {
      totalTokens: 0,
      organization: emptyOrganization(),
      quotas: emptyQuotas(),
    }
  }
  const org = (data.organization as Record<string, unknown> | undefined) ?? {}
  const tokenStats = data.token_stats as { total_tokens?: number } | undefined
  return {
    totalTokens: tokenStats?.total_tokens ?? 0,
    organization: {
      id: (org.id as number) ?? 0,
      name: (org.name as string) ?? '',
      code: (org.code as string) ?? '',
      invitation_code: (org.invitation_code as string) ?? '',
    },
    quotas: parseSchoolDashboardQuotas(
      data.quotas as Parameters<typeof parseSchoolDashboardQuotas>[0]
    ),
  }
}

export function useSchoolDashboardStats(
  orgId: Ref<number | null>,
  options?: { notifyOnError?: boolean }
) {
  const { t } = useLanguage()
  const query = useAdminSchoolStats(orgId)

  if (options?.notifyOnError !== false) {
    useQueryErrorNotification(query.error, () => t('admin.dashboardLoadError'))
  }

  const isLoading = computed(() => query.isFetching.value)

  const stats = computed(
    (): SchoolDashboardStats => mapStats(query.data.value as Record<string, unknown> | undefined)
  )

  const topUsers = computed((): SchoolDashboardTopUser[] => {
    const rows = query.data.value?.top_users
    if (!Array.isArray(rows)) {
      return []
    }
    return rows.map((row) => ({
      id: Number((row as Record<string, unknown>).id) || 0,
      name: String((row as Record<string, unknown>).name ?? ''),
      phone: String((row as Record<string, unknown>).phone ?? ''),
      total_tokens: Number((row as Record<string, unknown>).total_tokens ?? 0),
    }))
  })

  async function loadStats(): Promise<void> {
    if (orgId.value == null) {
      return
    }
    await query.refetch()
  }

  return {
    isLoading,
    stats,
    topUsers,
    loadStats,
  }
}
