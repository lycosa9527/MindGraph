import { createApp, nextTick, reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { createPinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import SettingsAccountPanels from '@/components/settings/SettingsAccountPanels.vue'

const { settings } = vi.hoisted(() => ({
  settings: {
    isBayiSsoSubject: false,
    needsSetLoginPassword: false,
    showAccountBindingsSection: true,
    canUseChromeExtension: false,
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
      showDingtalkBindSection: true,
      dingtalkBindingStatus: 'Not linked',
      dingtalkLinked: false,
      dingtalkBindLoading: false,
      canMintDingtalkBind: true,
      dingtalkStaffMasked: '',
      showBindDingTalkModal: false,
      showUnbindDingTalkModal: false,
      openBindDingTalkModal: vi.fn(),
      openUnbindDingTalkModal: vi.fn(),
      handleDingtalkBindCompleted: vi.fn(),
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
      accountLoginLabelKey: 'auth.accountIdMobile',
      accountLoginValue: '138****0000',
      canChangePhone: true,
      canUseApiToken: false,
      get canUseChromeExtension() {
        return settings.canUseChromeExtension
      },
      featureWordAddin: false,
      openclawSkillZipUrl: '/skill',
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

function mountPanel(section: 'security' | 'plugins' = 'security'): {
  app: ReturnType<typeof createApp>
  host: HTMLDivElement
  router: ReturnType<typeof createRouter>
  closed: { value: boolean }
} {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const closed = { value: false }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/browser-plugin', component: { template: '<div />' } },
    ],
  })
  const app = createApp(SettingsAccountPanels, {
    open: false,
    section,
    onClose: () => {
      closed.value = true
    },
  })
  app.use(createPinia())
  app.use(router)
  app.mount(host)
  return { app, host, router, closed }
}

function mountSecurityPanel(): { app: ReturnType<typeof createApp>; host: HTMLDivElement } {
  const { app, host } = mountPanel('security')
  return { app, host }
}

describe('settings security account bindings', () => {
  beforeEach(() => {
    settings.isBayiSsoSubject = false
    settings.needsSetLoginPassword = false
    settings.showAccountBindingsSection = true
    settings.canUseChromeExtension = false
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
    const dingtalk = host.querySelector('#account-binding-dingtalk')
    if (!dingtalk) {
      throw new Error('DingTalk bind row did not render under WeChat')
    }
    expect(follows(binding, dingtalk)).toBe(true)

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

  it('opens the browser plugin page instead of downloading the extension zip', async () => {
    settings.canUseChromeExtension = true
    const { app, host, router, closed } = mountPanel('plugins')
    await router.isReady()
    await nextTick()

    const plugins = host.querySelector('.space-y-4.user-settings-tab-pad')
    const button = plugins?.querySelector('button')
    if (!plugins || !button) {
      throw new Error('Chrome extension control did not render')
    }
    expect(button.hasAttribute('download')).toBe(false)
    expect(plugins.querySelector('a[href*="mindgraph-chrome-extension"]')).toBeNull()
    button.click()
    await vi.waitFor(() => {
      expect(router.currentRoute.value.path).toBe('/browser-plugin')
    })

    expect(closed.value).toBe(true)

    app.unmount()
    host.remove()
  })
})
