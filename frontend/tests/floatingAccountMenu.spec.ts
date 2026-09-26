import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('floating account menu', () => {
  it('does not mount on canvas layout', () => {
    const app = readSrc('src/App.vue')
    expect(app).toContain('showFloatingAccountMenu')
    expect(app).toContain("route.meta.layout !== 'canvas'")

    const menu = readSrc('src/components/sidebar/FloatingAccountMenu.vue')
    expect(menu).toContain('Not used on canvas')
  })
})
