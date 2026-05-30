/**
 * Shared school list for admin filters (user management header, edit user modal).
 */
import { ref } from 'vue'

import { apiRequest } from '@/utils/apiClient'

export interface AdminOrganizationOption {
  id: number
  name: string
  code: string
}

const organizations = ref<AdminOrganizationOption[]>([])
let loadPromise: Promise<void> | null = null

async function fetchOrganizations(): Promise<void> {
  const res = await apiRequest('/api/auth/admin/organizations')
  if (!res.ok) {
    return
  }
  const data = await res.json()
  if (!Array.isArray(data)) {
    organizations.value = []
    return
  }
  organizations.value = data.map((org: AdminOrganizationOption) => ({
    id: org.id,
    name: org.name,
    code: org.code,
  }))
}

export function useAdminOrganizationsList() {
  async function loadOrganizations(): Promise<void> {
    if (!loadPromise) {
      loadPromise = fetchOrganizations().finally(() => {
        loadPromise = null
      })
    }
    await loadPromise
  }

  return {
    organizations,
    loadOrganizations,
  }
}
