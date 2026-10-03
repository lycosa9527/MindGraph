import { createApp, nextTick, reactive } from 'vue'

import { createPinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsAccountPanels from '@/components/settings/SettingsAccountPanels.vue'

const { settings } = vi.hoisted(() => ({
  settings: {
    isBayiSsoSubject: false,
    needsSetLoginPassword: false,
    showAccountBindingsSection: true,
  },
}))

vi.mock('@/composables/core/useLanguage', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    currentLanguage: { value: 'zh' },
  }),
}))

vi.mock('@/components/settings/useAccountSettings', () => ({
  useAccountSettings: () =>
    reactive({
      t: (key: string) => key,
      authStore: { user: { phone: '13800000000' } },
      get isBayiSsoSubject() {
        return settings.isBayiSsoSubject
      },
      get needsSetLoginPassword() {
        return settings.needsSetLoginPassword
      },
      get showAccountBindingsSection() {
        return settings.showAccountBindingsSection
      },
      showWechatOAuthRow: true,
      wechatBindingStatus: 'Roy',
      wechatOAuthLinked: true,
      oauthLinksLoading: false,
      canBindWechat: false,
      unbindWechat: vi.fn(),
      openWechatBindModal: vi.fn(),
      showLoginDevicesModal: false,
      showAvatarModal: false,
      showChangePhoneModal: false,
      showSetPasswordSmsModal: false,
      showApiTokenModal: false,
      showOAuthBindModal: false,
      currentAvatarSrc: '',
      currentAvatar: '🐱',
      nameEdit: '',
      nameSaving: false,
      userPhone: '138****0000',
      canUseApiToken: false,
      canUseChromeExtension: false,
      featureWordAddin: false,
      openclawSkillZipUrl: '/skill',
      chromeExtensionZipUrl: '/ext',
      wordAddinZipUrl: '/word',
      fileReaderZipUrl: '/reader',
      openAvatarModal: vi.fn(),
      saveDisplayName: vi.fn(),
      openChangePhoneModal: vi.fn(),
      openSetPasswordSmsModal: vi.fn(),
      handleAvatarSuccess: vi.fn(),
      handlePhoneChangeSuccess: vi.fn(),
      handleOAuthBindSuccess: vi.fn(),
    }),
}))

function follows(earlier: Element, later: Element): boolean {
  const position = earlier.compareDocumentPosition(later)
  return (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
}

function mountSecurityPanel(): { app: ReturnType<typeof createApp>; host: HTMLDivElement } {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(SettingsAccountPanels, { open: false, section: 'security' })
  app.use(createPinia())
  app.mount(host)
  return { app, host }
}

describe('settings security account bindings', () => {
  beforeEach(() => {
    settings.isBayiSsoSubject = false
    settings.needsSetLoginPassword = false
    settings.showAccountBindingsSection = true
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

  it('renders WeChat linking above the password actions', async () => {
    const { app, host } = mountSecurityPanel()
    await nextTick()

    const form = host.querySelector('form')
    const binding = host.querySelector('#account-binding-wechat')
    const submit = host.querySelector('button[type="submit"]')
    if (!form || !binding || !submit) {
      throw new Error('security form did not render bindings and the confirm button')
    }
    expect(form.contains(binding)).toBe(true)
    expect(follows(binding, submit)).toBe(true)

    const devices = form.querySelector('.change-password-actions button[type="button"]')
    if (!devices) {
      throw new Error('login devices button is missing from the password actions')
    }
    expect(follows(binding, devices)).toBe(true)
    expect(host.querySelectorAll('#account-binding-wechat')).toHaveLength(1)

    app.unmount()
    host.remove()
  })

  it('keeps WeChat linking above login devices when the password form is hidden', async () => {
    settings.isBayiSsoSubject = true
    const { app, host } = mountSecurityPanel()
    await nextTick()

    const binding = host.querySelector('#account-binding-wechat')
    if (!binding) {
      throw new Error('account binding row did not render')
    }
    expect(host.querySelector('form')).toBeNull()
    const bindingBlock = binding.closest('.space-y-4')
    const devices = [...host.querySelectorAll('button')].find(
      (button) =>
        bindingBlock !== null && !bindingBlock.contains(button) && follows(binding, button)
    )
    if (!devices) {
      throw new Error('login devices button is missing below account bindings')
    }
    expect(follows(binding, devices)).toBe(true)
    expect(host.querySelectorAll('#account-binding-wechat')).toHaveLength(1)

    app.unmount()
    host.remove()
  })
})
