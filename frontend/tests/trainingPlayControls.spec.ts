import { createApp, h } from 'vue'

import { describe, expect, it, vi } from 'vitest'

import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
  }),
}))

function mountPad(props: Record<string, unknown> = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({
    render() {
      return h(TrainingPlayControls, props)
    },
  })
  app.mount(host)
  return { app, host }
}

describe('TrainingPlayControls', () => {
  it('keeps free/pull on the instructor pad by default', () => {
    const { app, host } = mountPad({ canPrev: true, canNext: true, mode: 'pull' })
    const group = host.querySelector('[role="radiogroup"]')
    const radios = host.querySelectorAll('[role="radio"]')
    expect(group).not.toBeNull()
    expect(radios).toHaveLength(2)
    expect(radios[0]?.getAttribute('aria-checked')).toBe('false')
    expect(radios[1]?.getAttribute('aria-checked')).toBe('true')
    expect(host.querySelector('.play-pad')).not.toBeNull()
    app.unmount()
    host.remove()
  })

  it('hides steer mode on local filmstrip preview', () => {
    const { app, host } = mountPad({ showMode: false })
    expect(host.querySelector('[role="radiogroup"]')).toBeNull()
    app.unmount()
    host.remove()
  })

  it('does not re-emit the already selected steer mode', () => {
    const onMode = vi.fn()
    const { app, host } = mountPad({ mode: 'pull', onMode })
    const radios = host.querySelectorAll<HTMLButtonElement>('[role="radio"]')
    radios[1]?.click()
    expect(onMode).not.toHaveBeenCalled()
    radios[0]?.click()
    expect(onMode).toHaveBeenCalledWith('free')
    app.unmount()
    host.remove()
  })
})
