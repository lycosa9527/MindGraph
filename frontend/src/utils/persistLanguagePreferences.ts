/**
 * Persist the current UI/prompt language for the signed-in user.
 * Call only from explicit user actions (settings, header toggle, locale hint).
 */
import { useAuthStore } from '@/stores/auth'
import { useUIStore } from '@/stores/ui'

export function persistLanguagePreferencesIfAuthenticated(): void {
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return
  }
  const uiStore = useUIStore()
  uiStore.setUiLanguageExplicit(true)
  const profile = authStore.user
  if (
    profile &&
    profile.uiLanguage === uiStore.language &&
    (profile.promptLanguage ?? uiStore.promptLanguage) === uiStore.promptLanguage &&
    (profile.matchPromptToUi ?? uiStore.matchPromptToUi) === uiStore.matchPromptToUi
  ) {
    return
  }
  void authStore.saveLanguagePreferences(uiStore.language, uiStore.promptLanguage, {
    matchPromptToUi: uiStore.matchPromptToUi,
  })
}
