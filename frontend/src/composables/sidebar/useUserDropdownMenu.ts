/**
 * Signed-in avatar menu functions configured under system settings.
 */
import { ref } from 'vue'

import type { TrainingCourse } from '@/types/training'
import { apiRequest } from '@/utils/apiClient'

export interface UserDropdownMenuEntry {
  id: string
  label: string
  course_id: string | null
  course_title: string
}

const items = ref<UserDropdownMenuEntry[]>([])
const openToken = ref(0)
const activeItemId = ref<string | null>(null)
let loaded = false

export function useUserDropdownMenu() {
  return { items, openToken, activeItemId, refreshUserDropdownMenu, openUserDropdownItem }
}

export async function refreshUserDropdownMenu(): Promise<void> {
  try {
    const res = await apiRequest('/api/auth/user-dropdown')
    if (!res.ok) return
    const body = (await res.json()) as { items?: UserDropdownMenuEntry[] }
    items.value = Array.isArray(body.items) ? body.items : []
    loaded = true
  } catch {
    items.value = []
  }
}

export async function ensureUserDropdownMenu(): Promise<void> {
  if (loaded) return
  await refreshUserDropdownMenu()
}

export function openUserDropdownItem(item: UserDropdownMenuEntry): void {
  activeItemId.value = item.id
  openToken.value += 1
}

export async function fetchUserDropdownCourse(itemId: string): Promise<TrainingCourse> {
  const res = await apiRequest(`/api/auth/user-dropdown/${encodeURIComponent(itemId)}/course`)
  if (!res.ok) throw new Error('course')
  return (await res.json()) as TrainingCourse
}
