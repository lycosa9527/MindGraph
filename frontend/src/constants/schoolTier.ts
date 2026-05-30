export type SchoolTier = 'lite' | 'standard' | 'professional'

export const SCHOOL_TIER_OPTIONS: readonly SchoolTier[] = [
  'lite',
  'standard',
  'professional',
] as const

export const SCHOOL_TIER_LIMITS: Record<
  SchoolTier,
  { memberLimit: number; managerLimit: number; diagramStorageGbPerMember: number }
> = {
  lite: { memberLimit: 50, managerLimit: 1, diagramStorageGbPerMember: 1 },
  standard: { memberLimit: 120, managerLimit: 3, diagramStorageGbPerMember: 2 },
  professional: { memberLimit: 200, managerLimit: 5, diagramStorageGbPerMember: 5 },
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

export function tierFeaturesForSchoolTier(
  tier: SchoolTier | null | undefined
): SchoolTierFeatures {
  if (!tier || tier === 'lite') {
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

export function normalizeSchoolTier(value: unknown): SchoolTier {
  const token = String(value ?? '').trim().toLowerCase()
  if (token === 'lite' || token === 'professional') {
    return token
  }
  return 'standard'
}
