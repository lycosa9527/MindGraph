/**
 * Superadmin org context — sync selected school with route query organization_id.
 */
import { computed, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores'

export const GLOBAL_ORG_SENTINEL = 0

export function useAdminOrgContext() {
  const route = useRoute()
  const router = useRouter()
  const authStore = useAuthStore()

  function parseQueryOrgId(): number {
    const raw = route.query.organization_id
    if (typeof raw === 'string' && raw.trim()) {
      const parsed = Number(raw)
      if (!Number.isNaN(parsed) && parsed > 0) {
        return parsed
      }
    }
    return GLOBAL_ORG_SENTINEL
  }

  const selectedOrgId = ref<number>(parseQueryOrgId())

  const routeOrgId = computed((): number | null => {
    const id = selectedOrgId.value
    if (id === GLOBAL_ORG_SENTINEL) {
      return null
    }
    return id
  })

  watch(
    () => route.query.organization_id,
    () => {
      const parsed = parseQueryOrgId()
      if (parsed !== selectedOrgId.value) {
        selectedOrgId.value = parsed
      }
    }
  )

  watch(selectedOrgId, (id) => {
    if (!authStore.isSuperAdmin) {
      return
    }
    const current = route.query.organization_id
    const next =
      id === GLOBAL_ORG_SENTINEL ? undefined : String(id)
    const currentNorm =
      typeof current === 'string' && current.trim() ? current : undefined
    if (next === currentNorm) {
      return
    }
    const query = { ...route.query }
    if (next == null) {
      delete query.organization_id
    } else {
      query.organization_id = next
    }
    void router.replace({ query })
  })

  return {
    selectedOrgId,
    routeOrgId,
    GLOBAL_ORG_SENTINEL,
  }
}
