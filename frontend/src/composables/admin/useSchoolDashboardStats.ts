/**
 * School-scoped dashboard stats for the management panel data center.
 */
import { ref, type Ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

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
  totalUsers: number
  totalTokens: number
  organization: SchoolDashboardOrganization
}

function emptyOrganization(): SchoolDashboardOrganization {
  return { id: 0, name: '', code: '', invitation_code: '' }
}

export function useSchoolDashboardStats(orgId: Ref<number | null>) {
  const { t } = useLanguage()
  const notify = useNotifications()

  const isLoading = ref(false)
  const stats = ref<SchoolDashboardStats>({
    totalUsers: 0,
    totalTokens: 0,
    organization: emptyOrganization(),
  })
  const topUsers = ref<SchoolDashboardTopUser[]>([])

  async function loadStats(): Promise<void> {
    const id = orgId.value
    if (id == null) {
      return
    }
    isLoading.value = true
    try {
      const res = await apiRequest(
        `/api/auth/admin/stats/school?organization_id=${id}`
      )
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        notify.error(httpErrorDetail(data) || t('admin.dashboardLoadError'))
        return
      }
      const data = await res.json()
      const org = data.organization ?? emptyOrganization()
      stats.value = {
        totalUsers: data.total_users ?? 0,
        totalTokens: data.token_stats?.total_tokens ?? 0,
        organization: {
          id: org.id ?? 0,
          name: org.name ?? '',
          code: org.code ?? '',
          invitation_code: org.invitation_code ?? '',
        },
      }
      topUsers.value = data.top_users ?? []
    } catch {
      notify.error(t('admin.dashboardLoadError'))
    } finally {
      isLoading.value = false
    }
  }

  watch(
    orgId,
    (id) => {
      if (id != null) {
        void loadStats()
      }
    },
    { immediate: true }
  )

  return {
    isLoading,
    stats,
    topUsers,
    loadStats,
  }
}
