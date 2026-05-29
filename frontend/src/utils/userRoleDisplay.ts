/**
 * User role display helpers — canonical slugs, legacy mapping, sidebar pill styles.
 */
import type { UserRole } from '@/types'

export const USER_ROLES = [
  'superadmin',
  'platform_bd',
  'expert',
  'school_admin',
  'teacher',
  'personal_trial',
  'personal_paid',
] as const satisfies readonly UserRole[]

const LEGACY_TO_CANONICAL: Record<string, UserRole> = {
  admin: 'superadmin',
  manager: 'school_admin',
  user: 'teacher',
}

export interface RolePillStyle {
  labelKey: string
  bgClass: string
  textClass: string
  borderClass: string
}

const ROLE_PILL_STYLES: Record<UserRole, RolePillStyle> = {
  superadmin: {
    labelKey: 'sidebar.roleSuperAdmin',
    bgClass: 'bg-rose-100',
    textClass: 'text-rose-800',
    borderClass: 'border-rose-200',
  },
  platform_bd: {
    labelKey: 'sidebar.rolePlatformAdmin',
    bgClass: 'bg-blue-100',
    textClass: 'text-blue-800',
    borderClass: 'border-blue-200',
  },
  expert: {
    labelKey: 'sidebar.roleExpert',
    bgClass: 'bg-violet-100',
    textClass: 'text-violet-800',
    borderClass: 'border-violet-200',
  },
  school_admin: {
    labelKey: 'sidebar.roleSchoolAdmin',
    bgClass: 'bg-teal-100',
    textClass: 'text-teal-800',
    borderClass: 'border-teal-200',
  },
  teacher: {
    labelKey: 'sidebar.roleSchoolEdition',
    bgClass: 'bg-stone-100',
    textClass: 'text-stone-700',
    borderClass: 'border-stone-200',
  },
  personal_trial: {
    labelKey: 'sidebar.roleTrialEdition',
    bgClass: 'bg-amber-100',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-200',
  },
  personal_paid: {
    labelKey: 'sidebar.roleSuperMember',
    bgClass: 'bg-yellow-100',
    textClass: 'text-yellow-900',
    borderClass: 'border-yellow-300',
  },
}

export function normalizeUserRole(role: string | undefined | null): UserRole {
  if (!role) {
    return 'teacher'
  }
  if (role in ROLE_PILL_STYLES) {
    return role as UserRole
  }
  return LEGACY_TO_CANONICAL[role] ?? 'teacher'
}

export function getRolePillStyle(role: string | undefined | null): RolePillStyle | null {
  const canonical = normalizeUserRole(role)
  return ROLE_PILL_STYLES[canonical] ?? null
}

export function isCanonicalUserRole(role: string): role is UserRole {
  return role in ROLE_PILL_STYLES
}
