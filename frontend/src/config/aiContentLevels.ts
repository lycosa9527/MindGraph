/**
 * AI content audience levels used by canvas generation and classroom narration.
 */
import { type EducationStage, buildEducationStageInstructions } from '@/constants/educationStage'

export const AI_CONTENT_LEVEL_IDS = [
  'general',
  'primary',
  'junior',
  'senior',
  'university',
  'adult',
  'expert',
] as const

export type AiContentLevelId = (typeof AI_CONTENT_LEVEL_IDS)[number]

export const DEFAULT_AI_CONTENT_LEVEL: AiContentLevelId = 'general'

const AI_CONTENT_LEVEL_STAGE: Record<AiContentLevelId, EducationStage | null> = {
  general: null,
  primary: '小学',
  junior: '初中',
  senior: '高中',
  university: '大学',
  adult: '成人',
  expert: '专家',
}

export function buildAiContentLevelInstructions(
  level: AiContentLevelId,
  language: string
): string | undefined {
  return buildEducationStageInstructions(AI_CONTENT_LEVEL_STAGE[level], language)
}

/** Accent color for the scope-style level picker (icon tint). */
export const AI_CONTENT_LEVEL_COLORS: Record<AiContentLevelId, string> = {
  general: '#10b981',
  primary: '#3b82f6',
  junior: '#f59e0b',
  senior: '#a855f7',
  university: '#06b6d4',
  adult: '#ec4899',
  expert: '#eab308',
}

export interface AiContentLevelPreference {
  level: AiContentLevelId
  /** False until the user explicitly picks a level in the UI. */
  userSet: boolean
}

export const DEFAULT_AI_CONTENT_LEVEL_PREFERENCE: AiContentLevelPreference = {
  level: DEFAULT_AI_CONTENT_LEVEL,
  userSet: false,
}

const STORAGE_KEY = 'mg-ai-content-level-v2'
const GENERATED_LEVEL_STORAGE_KEY = 'mg-ai-content-generated-levels'
const GUIDE_SEEN_STORAGE_KEY = 'mg-ai-content-level-guide-seen-v2'

export function isAiContentLevelId(value: unknown): value is AiContentLevelId {
  return typeof value === 'string' && (AI_CONTENT_LEVEL_IDS as readonly string[]).includes(value)
}

export function loadAiContentLevelPreference(): AiContentLevelPreference {
  if (typeof localStorage === 'undefined') {
    return { ...DEFAULT_AI_CONTENT_LEVEL_PREFERENCE }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_AI_CONTENT_LEVEL_PREFERENCE }
    const parsed = JSON.parse(raw) as {
      enabled?: boolean
      level?: unknown
      userSet?: unknown
    }
    // Legacy switch UI: disabled meant "never constrained".
    if (typeof parsed.enabled === 'boolean' && !parsed.enabled) {
      return { ...DEFAULT_AI_CONTENT_LEVEL_PREFERENCE }
    }
    const userSet = parsed.userSet === true || parsed.enabled === true
    // Until the user has chosen explicitly, always stay on 通用.
    if (!userSet) {
      return { ...DEFAULT_AI_CONTENT_LEVEL_PREFERENCE }
    }
    return {
      userSet: true,
      level: isAiContentLevelId(parsed.level) ? parsed.level : DEFAULT_AI_CONTENT_LEVEL,
    }
  } catch {
    return { ...DEFAULT_AI_CONTENT_LEVEL_PREFERENCE }
  }
}

export function saveAiContentLevelPreference(value: AiContentLevelPreference): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        level: value.level,
        userSet: value.userSet,
      } satisfies AiContentLevelPreference)
    )
  } catch {
    /* ignore quota / private mode */
  }
}

export function loadGeneratedLevelsByDiagram(): Record<string, AiContentLevelId> {
  if (typeof sessionStorage === 'undefined') return {}
  try {
    const raw = sessionStorage.getItem(GENERATED_LEVEL_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const out: Record<string, AiContentLevelId> = {}
    for (const [key, value] of Object.entries(parsed)) {
      if (isAiContentLevelId(value)) out[key] = value
    }
    return out
  } catch {
    return {}
  }
}

export function saveGeneratedLevelsByDiagram(value: Record<string, AiContentLevelId>): void {
  if (typeof sessionStorage === 'undefined') return
  try {
    sessionStorage.setItem(GENERATED_LEVEL_STORAGE_KEY, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

export function loadAiContentLevelGuideSeen(): boolean {
  if (typeof localStorage === 'undefined') return false
  try {
    return localStorage.getItem(GUIDE_SEEN_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function saveAiContentLevelGuideSeen(seen: boolean): void {
  if (typeof localStorage === 'undefined') return
  try {
    if (seen) {
      localStorage.setItem(GUIDE_SEEN_STORAGE_KEY, '1')
    } else {
      localStorage.removeItem(GUIDE_SEEN_STORAGE_KEY)
    }
  } catch {
    /* ignore */
  }
}
