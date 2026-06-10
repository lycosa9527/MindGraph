export type SchoolTier = 'trial' | 'lite' | 'standard' | 'professional'

/** Zero means no member cap (trial schools may have hundreds of teachers). */
export const SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED = 0

export const SCHOOL_TIER_OPTIONS: readonly SchoolTier[] = [
  'trial',
  'lite',
  'standard',
  'professional',
] as const

export const SCHOOL_TIER_LIMITS: Record<
  SchoolTier,
  {
    memberLimit: number
    managerLimit: number
    diagramStorageGbPerMember: number
    diagramsPerMember?: number
  }
> = {
  trial: {
    memberLimit: SCHOOL_TIER_MEMBER_LIMIT_UNLIMITED,
    managerLimit: 0,
    diagramStorageGbPerMember: 1,
    diagramsPerMember: 20,
  },
  lite: { memberLimit: 50, managerLimit: 1, diagramStorageGbPerMember: 1 },
  standard: { memberLimit: 120, managerLimit: 3, diagramStorageGbPerMember: 2 },
  professional: { memberLimit: 200, managerLimit: 5, diagramStorageGbPerMember: 5 },
}

/** Paid tiers have no per-user saved-diagram count cap (only trial is limited). */

export function isUnlimitedMemberLimit(limit: number): boolean {
  return limit <= 0
}

/** Trial tier sets manager_limit to 0 — school managers cannot be assigned. */
export function isManagerAssignmentUnavailable(limit: number): boolean {
  return limit <= 0
}

export interface SchoolTierFeatures {
  online_collab: boolean
  chrome_extension: boolean
  presentation_tools: boolean
  api_token: boolean
}

export const PREMIUM_SCHOOL_TIER_FEATURES: SchoolTierFeatures = {
  online_collab: true,
  chrome_extension: true,
  presentation_tools: true,
  api_token: true,
}

export const LITE_SCHOOL_TIER_FEATURES: SchoolTierFeatures = {
  online_collab: false,
  chrome_extension: false,
  presentation_tools: false,
  api_token: false,
}

/** Paid school tiers (superadmin-assigned); trial is the default experience edition. */
export function isPaidSchoolTier(tier: SchoolTier | null | undefined): boolean {
  return tier === 'lite' || tier === 'standard' || tier === 'professional'
}

export function tierFeaturesForSchoolTier(
  tier: SchoolTier | null | undefined
): SchoolTierFeatures {
  if (!tier || tier === 'trial' || tier === 'lite') {
    return LITE_SCHOOL_TIER_FEATURES
  }
  return PREMIUM_SCHOOL_TIER_FEATURES
}

/** Merge partial API flags with tier defaults (handles stale login payloads). */
export function mergeSchoolTierFeatures(
  tier: SchoolTier | null | undefined,
  fromApi: Partial<SchoolTierFeatures> | null | undefined
): SchoolTierFeatures {
  const base = tierFeaturesForSchoolTier(tier)
  if (!fromApi) {
    return base
  }
  return {
    online_collab: fromApi.online_collab ?? base.online_collab,
    chrome_extension: fromApi.chrome_extension ?? base.chrome_extension,
    presentation_tools: fromApi.presentation_tools ?? base.presentation_tools,
    api_token: fromApi.api_token ?? base.api_token,
  }
}

export const EXTRA_MEMBER_SEAT_PRESETS = [0, 10, 20, 50, 100] as const

export const EXTRA_MEMBER_SEATS_MAX = 500

export function effectiveMemberLimit(tier: SchoolTier, extraSeats: number): number {
  const base = SCHOOL_TIER_LIMITS[tier].memberLimit
  if (isUnlimitedMemberLimit(base)) {
    return base
  }
  const extra = Math.max(0, Math.min(Math.trunc(extraSeats), EXTRA_MEMBER_SEATS_MAX))
  return base + extra
}

export function normalizeSchoolTier(value: unknown): SchoolTier {
  const token = String(value ?? '').trim().toLowerCase()
  if (
    token === 'trial' ||
    token === 'lite' ||
    token === 'standard' ||
    token === 'professional'
  ) {
    return token
  }
  return 'trial'
}
