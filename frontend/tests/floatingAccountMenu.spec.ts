import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('floating account menu', () => {
  it('does not mount on canvas layout', () => {
    const app = readSrc('src/App.vue')
    expect(app).toContain('showFloatingAccountMenu')
    expect(app).toContain("route.meta.layout !== 'canvas'")

    const menu = readSrc('src/components/sidebar/FloatingAccountMenu.vue')
    expect(menu).toContain('Not used on canvas')
  })

  it('opens one Settings dialog from the user chip', () => {
    const footer = readSrc('src/components/sidebar/AppSidebarAccountFooter.vue')
    expect(footer).toContain('k="sidebar.settings"')
    expect(footer).not.toContain('k="sidebar.languageSettings"')
    expect(footer).not.toContain('k="auth.accountInfo"')
    expect(footer).toContain('openAccountModal')
    expect(footer).not.toContain('openLanguageSettingsModal')

    const tabs = readSrc('src/components/settings/userSettingsTabs.ts')
    expect(tabs).toContain("'settings.tabs.account'")
    expect(tabs).toContain("'settings.tabs.security'")
    expect(tabs).toContain("'settings.tabs.language'")
    expect(tabs).toContain("'settings.tabs.plugins'")
    expect(readSrc('src/components/settings/UserSettingsModal.vue')).toContain(
      'USER_SETTINGS_TAB_KEYS'
    )
  })
})
