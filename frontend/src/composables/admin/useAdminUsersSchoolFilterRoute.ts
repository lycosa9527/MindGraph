/**
 * Sync 用户管理 school filter with route organization_id (superadmin org context).
 */
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores'

export function useAdminUsersSchoolFilterRoute() {
  const route = useRoute()
  const router = useRouter()
  const authStore = useAuthStore()
  const orgFilter = ref<number | ''>('')

  function orgIdFromRoute(): number | '' {
    const raw = route.query.organization_id
    if (typeof raw === 'string' && raw.trim()) {
      const parsed = Number(raw)
      return Number.isFinite(parsed) ? parsed : ''
    }
    return ''
  }

  function syncOrgFilterToRoute(value: number | ''): void {
    const current = route.query.organization_id
    const next = value === '' ? undefined : String(value)
    const currentNorm =
      typeof current === 'string' && current.trim() ? current : undefined
    if (next === currentNorm) {
      return
    }
    const query: Record<string, string | string[]> = { ...route.query, tab: 'users' }
    if (next == null) {
      delete query.organization_id
    } else {
      query.organization_id = next
    }
    void router.replace({ query })
  }

  function onOrgFilterChange(value: number | ''): void {
    orgFilter.value = value
    if (authStore.isSuperAdmin) {
      syncOrgFilterToRoute(value)
    }
  }

  watch(
    () => route.query.organization_id,
    () => {
      if (!authStore.isSuperAdmin) {
        return
      }
      const normalized = orgIdFromRoute()
      if (orgFilter.value !== normalized) {
        orgFilter.value = normalized
      }
    },
    { immediate: true }
  )

  return {
    orgFilter,
    syncOrgFilterToRoute,
    onOrgFilterChange,
    orgIdFromRoute,
  }
}
