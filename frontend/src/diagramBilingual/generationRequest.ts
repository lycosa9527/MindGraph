/**
 * Languages for a full-diagram generate request.
 * Dual mode writes the interface language and the second interface language.
 * Branch expand, AI brainstorm, and explain stay on the primary language only.
 */
import { matchedPromptLanguageForUiLocale } from '@/i18n/locales'
import { useUIStore } from '@/stores/ui'

export function diagramGenerationLanguages(): {
  language: string
  secondaryLanguage?: string
} {
  const ui = useUIStore()
  if (!ui.bilingualUiEnabled) {
    return { language: ui.promptLanguage }
  }
  const language = matchedPromptLanguageForUiLocale(ui.language) ?? ui.promptLanguage
  const secondary = matchedPromptLanguageForUiLocale(ui.presenterUiLocale)
  if (secondary === null || secondary === language) {
    return { language }
  }
  return { language, secondaryLanguage: secondary }
}
