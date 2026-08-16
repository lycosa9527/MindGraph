/**
 * Mind-map 专业程度 prompts. Chinese and English are native templates,
 * not translations assembled from a shared slot list.
 */
import { type AiContentLevelId, DEFAULT_AI_CONTENT_LEVEL } from '@/config/aiContentLevels'
import { useAiContentLevelStore } from '@/stores/aiContentLevel'

import { MIND_MAP_AUDIENCE_EN } from './aiContentLevelInstructions.en'
import { MIND_MAP_AUDIENCE_ZH } from './aiContentLevelInstructions.zh'

function isChinesePromptLanguage(language: string): boolean {
  return language.toLowerCase().startsWith('zh')
}

export function buildMindMapAudienceInstructions(
  level: AiContentLevelId,
  language: string
): string | undefined {
  const templates = isChinesePromptLanguage(language) ? MIND_MAP_AUDIENCE_ZH : MIND_MAP_AUDIENCE_EN
  return templates[level]
}

export function resolveMindMapAudienceInstructions(language: string): string | undefined {
  const store = useAiContentLevelStore()
  if (!store.userSet || store.level === DEFAULT_AI_CONTENT_LEVEL) {
    return undefined
  }
  return buildMindMapAudienceInstructions(store.level, language)
}

export function mergeMindMapAudienceInstructions(
  audienceBlock: string | undefined,
  callerInstructions: string | undefined
): string | undefined {
  const audience = (audienceBlock ?? '').trim()
  const caller = (callerInstructions ?? '').trim()
  if (audience && caller) {
    return `${audience}\n\n${caller}`
  }
  if (audience) {
    return audience
  }
  if (caller) {
    return caller
  }
  return undefined
}
