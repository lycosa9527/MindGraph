/**
 * User role display helpers — canonical slugs, legacy mapping, sidebar pill styles.
 */
import type { SchoolTier, UserRole } from '@/types'
import { normalizeSchoolTier } from '@/constants/schoolTier'

export const USER_ROLES = [
  'superadmin',
  'platform_bd',
  'expert',
  'school_admin',
  'teacher',
  'personal_trial',
  'personal_paid',
] as const satisfies readonly UserRole[]

export const PLATFORM_USER_ROLES = ['superadmin', 'platform_bd', 'expert'] as const satisfies readonly UserRole[]

export const B2B_USER_ROLES = ['school_admin', 'teacher'] as const satisfies readonly UserRole[]

export const C2C_USER_ROLES = ['personal_trial', 'personal_paid'] as const satisfies readonly UserRole[]

export interface UserRolePillView {
  label: string
  bgClass: string
  textClass: string
  borderClass: string
}

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

/** Read effective school tier from an admin/school user list row. */
export function schoolTierFromUserRow(
  row: Record<string, unknown>
): SchoolTier | null | undefined {
  const raw = row.school_tier
  if (typeof raw !== 'string' || !raw.trim()) {
    return undefined
  }
  return normalizeSchoolTier(raw)
}

export function getRolePillStyle(
  role: string | undefined | null,
  schoolTier?: SchoolTier | null
): RolePillStyle | null {
  const canonical = normalizeUserRole(role)
  const tier = schoolTier != null ? normalizeSchoolTier(schoolTier) : null
  if (tier === 'trial' && canonical === 'teacher') {
    return ROLE_PILL_STYLES.personal_trial
  }
  return ROLE_PILL_STYLES[canonical] ?? null
}

export function isCanonicalUserRole(role: string): role is UserRole {
  return role in ROLE_PILL_STYLES
}

/** Localized role label (same keys as user table pills). */
export function userRoleLabel(
  translate: (key: string) => string,
  role: string | null | undefined,
  schoolTier?: SchoolTier | null
): string {
  const style = getRolePillStyle(role, schoolTier)
  return style ? translate(style.labelKey) : String(role ?? '—')
}

/** Pill view for table cells and role selects (labels match sidebar.role*). */
export function userRolePillView(
  translate: (key: string) => string,
  role: string | null | undefined,
  schoolTier?: SchoolTier | null
): UserRolePillView | null {
  const style = getRolePillStyle(role, schoolTier)
  if (!style) {
    return null
  }
  return {
    label: translate(style.labelKey),
    bgClass: style.bgClass,
    textClass: style.textClass,
    borderClass: style.borderClass,
  }
}

/** Options for role el-select (seven canonical roles). */
export function userRoleSelectOptions(
  translate: (key: string) => string
): Array<{ value: UserRole; label: string }> {
  return USER_ROLES.map((role) => ({
    value: role,
    label: userRoleLabel(translate, role),
  }))
}

export interface UserRoleSelectTier {
  tierLabelKey: string
  roles: readonly UserRole[]
}

/** Grouped role options (platform / B2B / C2C), same tiers as admin role assignment. */
export function userRoleSelectTiers(): readonly UserRoleSelectTier[] {
  return [
    { tierLabelKey: 'admin.roleTierPlatform', roles: PLATFORM_USER_ROLES },
    { tierLabelKey: 'admin.roleTierB2B', roles: B2B_USER_ROLES },
    { tierLabelKey: 'admin.roleTierC2C', roles: C2C_USER_ROLES },
  ]
}
