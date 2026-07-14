/**
 * Vite 8 / Rolldown: smoke imports for packages flagged in the upgrade audit.
 *
 * Uses dynamic import() throughout — same pattern as lazy app loads
 * (e.g. elementPlusLocale.ts, notifications.ts). Static imports are already
 * covered by unplugin-vue-components at build time; this file targets runtime
 * module resolution under Rolldown.
 *
 * Slow cold imports on /mnt/c are handled via the dedicated vitest project
 * in vitest.config.ts (testTimeout), not per-test workarounds.
 */
import { describe, expect, it } from 'vitest'

describe('Vite 8 module interop smoke', () => {
  it('imports vue3-carousel-3d named exports', async () => {
    const mod = await import('vue3-carousel-3d')
    expect(mod.Carousel3d).toBeDefined()
    expect(mod.Slide).toBeDefined()
  })

  it('imports mathlive', async () => {
    const mod = await import('mathlive')
    expect(mod).toBeTruthy()
  })

  it('imports html-to-image toPng', async () => {
    const mod = await import('html-to-image')
    expect(typeof mod.toPng).toBe('function')
  })

  it('imports element-plus button component via deep ESM path', async () => {
    const mod = await import('element-plus/es/components/button/index.mjs')
    expect(mod.ElButton).toBeDefined()
  })

  it('imports element-plus notification via deep ESM path', async () => {
    const mod = await import('element-plus/es/components/notification/index.mjs')
    expect(mod.ElNotification).toBeDefined()
  })

  it('imports element-plus locale via deep ESM path', async () => {
    const mod = await import('element-plus/es/locale/lang/en')
    expect(mod.default).toBeDefined()
  })
})
