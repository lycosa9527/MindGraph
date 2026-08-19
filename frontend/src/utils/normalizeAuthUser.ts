/**
 * Map login /me payloads (snake_case) or an already-normalized User to User.
 * Idempotent so login → setUser does not drop camelCase preference fields.
 */
import { isAiContentLevelId } from '@/config/aiContentLevels'
import { isEducationStage } from '@/constants/educationStage'
import { mergeSchoolTierFeatures, normalizeSchoolTier } from '@/constants/schoolTier'
import { coerceUiLocale } from '@/i18n/locales'
import type { BackendUser, DailyTokensSummary, SchoolTier, SchoolTierFeatures, User } from '@/types'
import { DEFAULT_USER_AVATAR_EMOJI } from '@/utils/userAvatarEmoji'
import { normalizeUserRole } from '@/utils/userRoleDisplay'

export type AuthUserSource = BackendUser & Partial<User>

function firstNonEmptyString(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.length > 0) {
      return value
    }
  }
  return null
}

function resolveAllowsSimplifiedChinese(source: AuthUserSource): boolean {
  if (source.allows_simplified_chinese === false || source.allowsSimplifiedChinese === false) {
    return false
  }
  return true
}

function resolveMatchPromptToUi(source: AuthUserSource): boolean | undefined {
  if (typeof source.match_prompt_to_ui === 'boolean') {
    return source.match_prompt_to_ui
  }
  if (typeof source.matchPromptToUi === 'boolean') {
    return source.matchPromptToUi
  }
  return undefined
}

function resolveLoginPasswordSet(source: AuthUserSource): boolean {
  if (source.login_password_set !== undefined) {
    return Boolean(source.login_password_set)
  }
  if (source.loginPasswordSet !== undefined) {
    return Boolean(source.loginPasswordSet)
  }
  return true
}

function resolveThinkingCoins(source: AuthUserSource): User['thinkingCoins'] {
  const raw = source.thinking_coins ?? source.thinkingCoins
  if (!raw || typeof raw !== 'object') {
    return undefined
  }
  return {
    balance: Number(raw.balance ?? 0),
    eligible: raw.eligible === true,
  }
}

function readFiniteNumber(raw: Record<string, unknown>, keys: readonly string[]): number {
  for (const key of keys) {
    const value = raw[key]
    const parsed = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return 0
}

function resolveDailyTokens(source: AuthUserSource): DailyTokensSummary | undefined {
  const raw = source.daily_tokens ?? source.dailyTokens
  if (!raw || typeof raw !== 'object') {
    return undefined
  }
  const record = raw as Record<string, unknown>
  return {
    cap: readFiniteNumber(record, ['cap']),
    usedToday: readFiniteNumber(record, ['used_today', 'usedToday']),
    remainingToday: readFiniteNumber(record, ['remaining_today', 'remainingToday']),
  }
}

export function normalizeAuthUser(source: BackendUser | User): User {
  const raw = source as AuthUserSource
  let avatar = raw.avatar || DEFAULT_USER_AVATAR_EMOJI
  if (avatar.startsWith('avatar_')) {
    avatar = DEFAULT_USER_AVATAR_EMOJI
  }

  const org = raw.organization
  const orgIsObject = typeof org === 'object' && org !== null
  const orgId = orgIsObject ? org.id : undefined
  const orgName = orgIsObject ? org.name : typeof org === 'string' ? org : undefined
  const orgDisplayNameRaw =
    orgIsObject && org.display_name != null ? String(org.display_name).trim() : ''
  const orgDisplayName = orgDisplayNameRaw || undefined
  const mindmateNameRaw =
    orgIsObject && org.mindmate_agent_name != null ? String(org.mindmate_agent_name).trim() : ''
  const mindmateAgentName = mindmateNameRaw || raw.mindmateAgentName || undefined
  const mindmateAvatarRaw =
    orgIsObject && org.mindmate_agent_avatar_url != null
      ? String(org.mindmate_agent_avatar_url).trim()
      : ''
  const mindmateAgentAvatarUrl = mindmateAvatarRaw || raw.mindmateAgentAvatarUrl || undefined
  const schoolTierRaw =
    orgIsObject && org.school_tier != null ? normalizeSchoolTier(org.school_tier) : undefined
  const schoolTierFeaturesRaw =
    orgIsObject && org.school_tier_features != null ? org.school_tier_features : undefined
  const schoolTier: SchoolTier | undefined = orgId
    ? (schoolTierRaw ?? 'trial')
    : (raw.schoolTier ?? undefined)
  const schoolTierFeatures: SchoolTierFeatures | undefined = orgId
    ? mergeSchoolTierFeatures(schoolTier, schoolTierFeaturesRaw)
    : (raw.schoolTierFeatures ?? undefined)
  const subscriptionExpired = orgIsObject
    ? org.subscription_expired === true
    : raw.subscriptionExpired === true
  const displayLabel = orgDisplayName || orgName || raw.schoolName || ''

  const allowsZh = resolveAllowsSimplifiedChinese(raw)
  let uiLang = firstNonEmptyString(raw.ui_language, raw.uiLanguage)
  const coercedUi = coerceUiLocale(uiLang)
  if (coercedUi !== null) {
    uiLang = coercedUi
  }
  let promptLang = firstNonEmptyString(raw.prompt_language, raw.promptLanguage)
  if (!allowsZh) {
    if ((uiLang || '').toLowerCase() === 'zh') {
      uiLang = 'en'
    }
    if ((promptLang || '').toLowerCase() === 'zh') {
      promptLang = 'en'
    }
  }

  const educationRaw = raw.education_stage ?? raw.educationStage ?? null
  const aiLevelRaw = raw.ai_content_level ?? raw.aiContentLevel ?? null

  return {
    id: String(raw.id || raw.user?.id || ''),
    username: raw.name || raw.username || raw.phone || raw.email || '',
    phone: raw.phone || raw.user?.phone || '',
    email: raw.email,
    role: normalizeUserRole(raw.role),
    schoolId: orgId ? String(orgId) : raw.schoolId,
    schoolName: displayLabel,
    avatar,
    createdAt: raw.created_at || raw.createdAt,
    lastLogin: raw.last_login || raw.lastLogin,
    uiLanguage: uiLang,
    promptLanguage: promptLang,
    matchPromptToUi: resolveMatchPromptToUi(raw),
    uiVersion: raw.ui_version ?? raw.uiVersion ?? null,
    educationStage: isEducationStage(educationRaw) ? educationRaw : null,
    aiContentLevel: isAiContentLevelId(aiLevelRaw) ? aiLevelRaw : null,
    allowsSimplifiedChinese: allowsZh,
    loginPasswordSet: resolveLoginPasswordSet(raw),
    mindmateAgentName: mindmateAgentName || null,
    mindmateAgentAvatarUrl: mindmateAgentAvatarUrl || null,
    schoolTier: schoolTier ?? null,
    schoolTierFeatures: schoolTierFeatures ?? null,
    subscriptionExpired: subscriptionExpired ?? false,
    thinkingCoins: resolveThinkingCoins(raw),
    dailyTokens: resolveDailyTokens(raw),
  }
}
