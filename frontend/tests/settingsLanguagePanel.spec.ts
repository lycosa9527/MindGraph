import { createApp, nextTick } from 'vue'

import { createPinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsLanguagePanel from '@/components/settings/SettingsLanguagePanel.vue'
import zhCommon from '@/locales/messages/zh/common'

function mountLanguagePanel(): { app: ReturnType<typeof createApp>; host: HTMLDivElement } {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(SettingsLanguagePanel, { open: true })
  app.use(createPinia())
  app.mount(host)
  return { app, host }
}

describe('settings language panel', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
  })

  it('keeps interface language first and follows it for LLM output', async () => {
    const { app, host } = mountLanguagePanel()
    await nextTick()

    expect(zhCommon['settings.language.matchPrompt']).toBe('与界面语言一致')

    const text = host.textContent ?? ''
    expect(text).toContain('Interface language')
    expect(text).toContain('LLM output language')
    expect(text).toContain('Same as the interface language')
    expect(text).not.toContain('virtual keyboard')
    expect(text).not.toContain('Primary language')
    expect(text).not.toContain('When on, buttons, tooltips, and modal chrome')
    expect(text.indexOf('Interface language')).toBeLessThan(text.indexOf('LLM output language'))
    expect(text.indexOf('LLM output language')).toBeLessThan(
      text.indexOf('Same as the interface language')
    )
    const preview = host.querySelector('.language-settings-preview')
    const controls = host.querySelector('.language-settings-swiss__stack')
    if (!preview || !controls) {
      throw new Error('language preview did not render beside the controls')
    }
    expect(preview.textContent).toContain('Central Topic')
    expect(preview.textContent).toContain('Topic A')
    expect(preview.textContent).toContain('Undo')
    expect(preview.textContent).not.toContain('Add Node')
    expect(
      (controls.compareDocumentPosition(preview) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
    ).toBe(true)
    expect(host.querySelectorAll('el-select, .el-select')).toHaveLength(2)

    const follow = [...host.querySelectorAll('label')].find((label) =>
      (label.textContent ?? '').includes('Same as the interface language')
    )
    const input = follow?.querySelector('input')
    if (!input) {
      throw new Error('follow-interface checkbox did not render')
    }
    expect((input as HTMLInputElement).checked).toBe(true)
    const promptSelect = host.querySelector('.language-settings-swiss__follow-select')
    expect(promptSelect?.getAttribute('disabled')).not.toBe('false')
    input.click()
    await nextTick()

    expect(promptSelect?.getAttribute('disabled')).toBe('false')
    expect(host.querySelectorAll('el-select, .el-select')).toHaveLength(2)

    const bilingualOn = [...host.querySelectorAll('button')].find(
      (button) => (button.textContent ?? '').trim() === 'On'
    )
    if (!bilingualOn) {
      throw new Error('bilingual toggle did not render')
    }
    bilingualOn.click()
    await nextTick()

    const after = host.textContent ?? ''
    expect(after).toContain('UI primary language')
    expect(after).toContain('UI secondary language')
    expect(after).not.toContain('LLM output language')
    expect(after).not.toContain('Same as the interface language')
    expect(after.indexOf('Bilingual interface')).toBeLessThan(after.indexOf('UI primary language'))
    expect(after.indexOf('UI primary language')).toBeLessThan(
      after.indexOf('UI secondary language')
    )
    expect(host.querySelectorAll('el-select, .el-select')).toHaveLength(2)

    app.unmount()
    host.remove()
  })
})
