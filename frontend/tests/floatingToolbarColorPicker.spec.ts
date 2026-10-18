import { createApp, h } from 'vue'

import { describe, expect, it } from 'vitest'

import FloatingToolbarColorPicker from '@/components/canvas/FloatingToolbarColorPicker.vue'

function mountPicker(currentColor: string, nativeColor: string) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp({
    render() {
      return h(FloatingToolbarColorPicker, { currentColor, nativeColor })
    },
  })
  app.mount(host)
  return { app, host }
}

describe('FloatingToolbarColorPicker', () => {
  it('highlights the painted fill and binds it to the native well', () => {
    const { app, host } = mountPicker('#E7F6FD', '#e7f6fd')
    const active = host.querySelector('.nft-palette-swatch--active') as HTMLElement | null
    expect(active).not.toBeNull()
    expect(active?.style.backgroundColor).toBe('rgb(231, 246, 253)')
    expect(active?.getAttribute('aria-pressed')).toBe('true')
    const well = host.querySelector('input[type="color"]') as HTMLInputElement | null
    expect(well?.value).toBe('#e7f6fd')
    app.unmount()
    host.remove()
  })

  it('does not mark the white or black chips when the node is a theme fill', () => {
    const { app, host } = mountPicker('#E7F6FD', '#e7f6fd')
    const active = [...host.querySelectorAll('.nft-palette-swatch--active')]
    expect(active).toHaveLength(1)
    expect((active[0] as HTMLElement).style.backgroundColor).not.toBe('rgb(255, 255, 255)')
    expect((active[0] as HTMLElement).style.backgroundColor).not.toBe('rgb(0, 0, 0)')
    app.unmount()
    host.remove()
  })
})
