/** Tabs in the unified user Settings dialog. */
export type UserSettingsTab = 'account' | 'security' | 'language' | 'plugins' | 'knowledge'

export const USER_SETTINGS_TAB_KEYS: Record<UserSettingsTab, string> = {
  account: 'settings.tabs.account',
  security: 'settings.tabs.security',
  language: 'settings.tabs.language',
  plugins: 'settings.tabs.plugins',
  knowledge: 'settings.tabs.knowledge',
}
