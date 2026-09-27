/**
 * Admin API for functions in the signed-in user avatar menu.
 */
import { useQuery } from '@tanstack/vue-query'

import { adminFetchJson } from '@/composables/queries/adminApi'
import { adminKeys } from '@/composables/queries/adminKeys'

export interface UserDropdownItemRow {
  id: string
  label: string
  course_id: string | null
  course_title: string
  sort_order: number
}

export interface UserDropdownCourseOption {
  id: string
  title: string
  status: string
}

export interface UserDropdownCatalog {
  items: UserDropdownItemRow[]
  courses: UserDropdownCourseOption[]
}

const BASE = '/api/auth/admin/user-dropdown'

export function useAdminUserDropdown() {
  return useQuery({
    queryKey: adminKeys.userDropdown(),
    queryFn: () => adminFetchJson<UserDropdownCatalog>(BASE, {}, 'Failed to load user menu'),
  })
}

export async function createUserDropdownItem(label: string): Promise<UserDropdownCatalog> {
  return adminFetchJson<UserDropdownCatalog>(
    BASE,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label }),
    },
    'Failed to add menu function'
  )
}

export async function patchUserDropdownItem(
  itemId: string,
  body: { label?: string; course_id?: string | null }
): Promise<UserDropdownCatalog> {
  return adminFetchJson<UserDropdownCatalog>(
    `${BASE}/${encodeURIComponent(itemId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    'Failed to save menu function'
  )
}

export async function deleteUserDropdownItem(itemId: string): Promise<UserDropdownCatalog> {
  return adminFetchJson<UserDropdownCatalog>(
    `${BASE}/${encodeURIComponent(itemId)}`,
    { method: 'DELETE' },
    'Failed to delete menu function'
  )
}
