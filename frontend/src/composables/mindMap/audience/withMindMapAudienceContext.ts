/**
 * Attach mind-map 专业程度 text to generate / palette / explain payloads.
 */
import { resolveMindMapAudienceInstructions } from '@/composables/mindMap/audience/aiContentLevelInstructions'
import { useUIStore } from '@/stores/ui'

function promptLanguage(): string {
  return useUIStore().promptLanguage
}

function mergeEducationalContext(existing: unknown, rawMessage: string): Record<string, unknown> {
  if (existing && typeof existing === 'object' && !Array.isArray(existing)) {
    return { ...(existing as Record<string, unknown>), raw_message: rawMessage }
  }
  return { raw_message: rawMessage }
}

export function withMindMapAudienceContext(
  payload: Record<string, unknown>,
  language?: string
): Record<string, unknown> {
  const block = resolveMindMapAudienceInstructions(language ?? promptLanguage())
  if (!block) {
    return payload
  }
  const existingGen =
    typeof payload.generation_instructions === 'string'
      ? payload.generation_instructions.trim()
      : ''
  return {
    ...payload,
    educational_context: mergeEducationalContext(payload.educational_context, block),
    generation_instructions: existingGen ? `${block}\n\n${existingGen}` : block,
  }
}

export function appendMindMapAudienceFormField(formData: FormData, language?: string): void {
  const block = resolveMindMapAudienceInstructions(language ?? promptLanguage())
  if (!block) {
    return
  }
  formData.append('generation_instructions', block)
}
