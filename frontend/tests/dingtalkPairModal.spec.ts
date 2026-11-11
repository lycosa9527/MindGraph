import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createApp, defineComponent, nextTick, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import DingTalkPairModal from '@/components/auth/DingTalkPairModal.vue'

const authFetch = vi.hoisted(() => vi.fn())

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
  useNotifications: () => ({
    warningKey: vi.fn(),
    errorKey: vi.fn(),
    successKey: vi.fn(),
  }),
}))

vi.mock('@tanstack/vue-query', () => ({
  useQueryClient: () => ({
    invalidateQueries: vi.fn(),
  }),
}))

vi.mock('@/utils/api', () => ({
  authFetch: (...args: unknown[]) => authFetch(...args),
}))

vi.mock('@/components/common/SwissGlassDialog.vue', () => ({
  default: {
    name: 'SwissGlassDialog',
    props: ['modelValue'],
    emits: ['update:modelValue', 'close'],
    template: '<div class="stub-dialog"><slot /><slot name="footer" /></div>',
  },
}))

vi.mock('@/components/common/I18nText.vue', () => ({
  default: {
    props: ['k'],
    template: '<span>{{ k }}</span>',
  },
}))

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

describe('DingTalkPairModal', () => {
  let host: HTMLDivElement

  beforeEach(() => {
    host = document.createElement('div')
    document.body.appendChild(host)
    authFetch.mockReset()
    authFetch.mockImplementation(async (url: string) => {
      if (url.includes('/dingtalk-bind/start') || url.includes('/unbind/start')) {
        return jsonResponse({
          token: 'bind-token-abcdefghijklmnopqrstuvwxyz',
          ttl_seconds: 600,
        })
      }
      if (url.includes('/room-code')) {
        return jsonResponse({
          code: '123456',
          code_display: '123-456',
          valid_until_unix: Math.floor(Date.now() / 1000) + 30,
        })
      }
      return jsonResponse({})
    })
  })

  function callsTo(fragment: string): unknown[][] {
    return authFetch.mock.calls.filter((call) => String(call[0]).includes(fragment))
  }

  async function settle(): Promise<void> {
    await vi.waitFor(() => {
      expect(host.textContent).toContain('123-456')
    })
  }

  it('keeps the settings dialogs mounted and toggles them with v-model', () => {
    const source = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), '../src/components/settings/SettingsAccountPanels.vue'),
      'utf8'
    )
    expect(source).toContain('v-model="form.showBindDingTalkModal"')
    expect(source).toContain('v-model="form.showUnbindDingTalkModal"')
    expect(source).not.toContain('v-if="form.showBindDingTalkModal"')
    expect(source).not.toContain('v-if="form.showUnbindDingTalkModal"')
  })

  it('mints one pair code when the dialog mounts already open', async () => {
    const app = createApp(DingTalkPairModal, {
      modelValue: true,
      mode: 'bind',
    })
    app.mount(host)
    await settle()
    expect(callsTo('/dingtalk-bind/start')).toHaveLength(1)
    app.unmount()
    expect(callsTo('/dingtalk-bind/cancel')).toHaveLength(1)
    host.remove()
  })

  it('mints on open and cancels on close while the dialog stays mounted', async () => {
    const Harness = defineComponent({
      components: { DingTalkPairModal },
      setup() {
        const open = ref(false)
        return { open }
      },
      template:
        '<button id="open-pair" type="button" @click="open = true">open</button>' +
        '<button id="close-pair" type="button" @click="open = false">close</button>' +
        '<DingTalkPairModal v-model="open" mode="bind" />',
    })
    const app = createApp(Harness)
    app.mount(host)
    await nextTick()
    expect(authFetch).not.toHaveBeenCalled()
    host.querySelector<HTMLButtonElement>('#open-pair')?.click()
    await settle()
    expect(callsTo('/dingtalk-bind/start')).toHaveLength(1)
    host.querySelector<HTMLButtonElement>('#close-pair')?.click()
    await nextTick()
    expect(callsTo('/dingtalk-bind/cancel')).toHaveLength(1)
    app.unmount()
    expect(callsTo('/dingtalk-bind/cancel')).toHaveLength(1)
    host.remove()
  })

  it('cancels a mint that finishes after the dialog has closed', async () => {
    let releaseStart: (value: void) => void = () => {}
    const started = new Promise<void>((resolve) => {
      releaseStart = resolve
    })
    authFetch.mockImplementation(async (url: string) => {
      if (String(url).includes('/dingtalk-bind/start')) {
        await started
        return jsonResponse({
          token: 'late-token-abcdefghijklmnopqrstuvwxyz',
          ttl_seconds: 600,
        })
      }
      return jsonResponse({})
    })
    const Harness = defineComponent({
      components: { DingTalkPairModal },
      setup() {
        const open = ref(false)
        return { open }
      },
      template:
        '<button id="open-pair" type="button" @click="open = true">open</button>' +
        '<button id="close-pair" type="button" @click="open = false">close</button>' +
        '<DingTalkPairModal v-model="open" mode="bind" />',
    })
    const app = createApp(Harness)
    app.mount(host)
    host.querySelector<HTMLButtonElement>('#open-pair')?.click()
    await nextTick()
    host.querySelector<HTMLButtonElement>('#close-pair')?.click()
    await nextTick()
    releaseStart()
    await vi.waitFor(() => {
      const scoped = authFetch.mock.calls.find((call) => {
        const init = call[1] as RequestInit | undefined
        return String(call[0]).includes('/cancel') && typeof init?.body === 'string'
      })
      expect(scoped).toBeTruthy()
    })
    const scoped = authFetch.mock.calls.find((call) => {
      const init = call[1] as RequestInit | undefined
      return String(call[0]).includes('/cancel') && typeof init?.body === 'string'
    })
    expect(JSON.parse(String((scoped?.[1] as RequestInit).body))).toEqual({
      token: 'late-token-abcdefghijklmnopqrstuvwxyz',
    })
    app.unmount()
    host.remove()
  })
})
