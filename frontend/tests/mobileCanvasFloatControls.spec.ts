import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('mobile canvas float controls', () => {
  it('stacks fit-to-screen above undo', () => {
    const page = readSrc('src/pages/mobile/MobileCanvasPage.vue')
    const stack = page.slice(
      page.indexOf('class="mobile-zoom-controls'),
      page.indexOf('</div>', page.indexOf('mobile-canvas-undo'))
    )
    const fit = stack.indexOf('data-testid="mobile-canvas-fit"')
    const undo = stack.indexOf('data-testid="mobile-canvas-undo"')
    expect(fit).toBeGreaterThan(-1)
    expect(undo).toBeGreaterThan(fit)
    expect(stack).toContain("t('canvas.zoomControls.fitCanvas')")
    expect(stack).toContain('handleFitToScreen')
    expect(stack).toContain('<Maximize2')
    expect(stack).toContain("t('canvas.toolbar.undo')")
    expect(stack).toContain('handleUndo')
    expect(stack).toContain('<Undo2')
    expect(stack).not.toContain('zoomReset')
    expect(stack).not.toContain('RotateCcw')
  })

  it('undo uses the diagram history guard', () => {
    const toolbar = readSrc('src/composables/mobile/useMobileCanvasToolbar.ts')
    expect(toolbar).toContain('tryCollabGuardedUndo()')
    expect(toolbar).not.toContain('view:zoom_reset_requested')
  })
})
