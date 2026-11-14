/**
 * Session-scoped custom seminar role labels shared by all role pickers.
 */
import { ref } from 'vue'

import { isSeminarCustomRole, normalizeSeminarBriefRole } from '@/utils/mindmateSeminarBrief'

/** Reactive list — import this ref so pickers update when roles are added. */
export const seminarCustomRoles = ref<string[]>([])

export function rememberSeminarCustomRole(role: string): string | null {
  const next = normalizeSeminarBriefRole(role)
  if (!isSeminarCustomRole(next)) {
    return null
  }
  if (!seminarCustomRoles.value.includes(next)) {
    seminarCustomRoles.value = [...seminarCustomRoles.value, next]
  }
  return next
}

export function syncSeminarCustomRoles(roles: Iterable<string>): void {
  const merged = new Set(seminarCustomRoles.value)
  for (const raw of roles) {
    const next = normalizeSeminarBriefRole(raw)
    if (isSeminarCustomRole(next)) {
      merged.add(next)
    }
  }
  seminarCustomRoles.value = [...merged]
}

export function clearSeminarCustomRoles(): void {
  seminarCustomRoles.value = []
}
