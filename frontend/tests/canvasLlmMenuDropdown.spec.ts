import { createApp, nextTick } from 'vue'

import { createPinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import CanvasLlmMenuDropdown from '@/canvas-ribbon/CanvasLlmMenuDropdown.vue'

vi.mock('@/utils/apiClient', () => ({
  apiRequestJson: vi.fn(async () => ({
    models: {
      express: 'deepseek-v4.1-flash',
      'qwen3.8-flash': 'qwen3.8-flash',
      'qwen3-max': 'qwen3.8-max',
      kimi: 'glm-5-3-flash',
      doubao21: 'doubao-seed-2-1-turbo',
    },
  })),
}))

describe('CanvasLlmMenuDropdown', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      media: '',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  })

  it('shows the DeepSeek mark and Express until the user opens the model list', async () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp(CanvasLlmMenuDropdown, { testId: 'mobile-canvas-llm-menu', touch: true })
    app.use(createPinia())
    app.mount(host)
    await nextTick()

    const button = host.querySelector('.mm-llm-menu-btn')
    expect(button?.getAttribute('data-llm')).toBe('express')
    expect(button?.querySelector('[fill="#4D6BFE"]')).toBeTruthy()
    expect(button?.querySelector('.mm-llm-menu-btn__label')?.textContent).toBe('Express')
    expect(host.querySelector('[data-testid="mobile-canvas-llm-menu"]')).toBeTruthy()

    button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()

    const menuText = document.body.textContent ?? ''
    expect(menuText).toContain('Express')
    expect(menuText).toContain('Balanced')
    expect(menuText).toContain('Max')
    expect(menuText).toContain('Doubao')
    expect(menuText).toContain('deepseek-v4.1-flash')

    app.unmount()
    host.remove()
  })
})
