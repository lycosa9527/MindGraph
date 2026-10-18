import { createApp, nextTick } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import MindmateHeader from '@/components/panels/mindmate/MindmateHeader.vue'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    currentLanguage: { value: 'en' },
  }),
}))

vi.mock('@/components/common/I18nText.vue', () => ({
  default: {
    props: ['k'],
    template: '<span>{{ k }}</span>',
  },
}))

describe('MindmateHeader continue session', () => {
  let host: HTMLElement

  beforeEach(() => {
    host = document.createElement('div')
    document.body.appendChild(host)
  })

  it('shows Continue session on a closed seminar and emits when clicked', async () => {
    const emitted: string[] = []
    const app = createApp(MindmateHeader, {
      showContinueSession: true,
      mode: 'fullpage',
      onContinueSession: () => {
        emitted.push('continue')
      },
    })
    app.mount(host)
    await nextTick()
    const button = [...host.querySelectorAll('button')].find((node) =>
      node.textContent?.includes('mindmate.collabContinueSession')
    )
    expect(button).toBeTruthy()
    button?.click()
    await nextTick()
    expect(emitted).toEqual(['continue'])
    app.unmount()
    host.remove()
  })

  it('hides Continue session while the seminar is still open', async () => {
    const app = createApp(MindmateHeader, {
      showContinueSession: false,
      mode: 'fullpage',
    })
    app.mount(host)
    await nextTick()
    const button = [...host.querySelectorAll('button')].find((node) =>
      node.textContent?.includes('mindmate.collabContinueSession')
    )
    expect(button).toBeUndefined()
    app.unmount()
    host.remove()
  })
})
