/**
 * Surfaces must not call Redis hub persist / updateContext directly —
 * edit turns and hub sync go through pipeline workers.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/** Vitest cwd is frontend/; avoid import.meta.url (may not be file: under the runner). */
const frontendSrc = resolve(process.cwd(), 'src')

const SURFACE_FILES = [
  'composables/mobile/useMobileKittyChat.ts',
  'composables/canvasToolbar/useMindMapOneSentenceChat.ts',
  'composables/kitty/useMobileKittyPairing.ts',
  'pages/mobile/MobileKittyPage.vue',
] as const

function readSurface(rel: string): string {
  return readFileSync(resolve(frontendSrc, rel), 'utf8')
}

describe('kitty surface import guards', () => {
  it('chat/pairing surfaces do not import diagramEditHubPersist runtime APIs', () => {
    for (const rel of SURFACE_FILES) {
      const src = readSurface(rel)
      expect(src, rel).not.toMatch(
        /from\s+['"]@\/composables\/kitty\/diagramEditHubPersist['"]/
      )
      expect(src, rel).not.toMatch(
        /persistVerifiedDiagramToHub\s*\(/
      )
    }
  })

  it('chat/pairing surfaces do not call syncKittyHubContext directly', () => {
    for (const rel of SURFACE_FILES) {
      const src = readSurface(rel)
      expect(src, rel).not.toMatch(/syncKittyHubContext\s*\(/)
    }
  })

  it('pipeline Eruda path uses #trace not competing #hub in chat/persist workers', () => {
    const chat = readSurface('composables/mobile/useMobileKittyChat.ts')
    expect(chat).toMatch(/'#trace'/)
    expect(chat).not.toMatch(/'#hub'/)

    const persist = readSurface('composables/kitty/useKittyMobileHubPersist.ts')
    expect(persist).not.toMatch(/'#hub'/)
    expect(persist).toMatch(/S15_library_persist/)

    const sync = readSurface('composables/kitty/syncKittyHubContext.ts')
    expect(sync).not.toMatch(/'#hub'/)
  })

  it('edit chat surfaces route text inbound through runKittyEditTurn', () => {
    for (const rel of [
      'composables/mobile/useMobileKittyChat.ts',
      'composables/canvasToolbar/useMindMapOneSentenceChat.ts',
    ] as const) {
      const src = readSurface(rel)
      expect(src, rel).toMatch(/runKittyEditTurn\s*\(/)
      expect(src, rel).not.toMatch(/\.sendTextMessage\s*\(/)
    }
  })

  it('desktop and mobile chat share useKittyAsrSession', () => {
    for (const rel of [
      'composables/mobile/useMobileKittyChat.ts',
      'composables/canvasToolbar/useMindMapOneSentenceChat.ts',
    ] as const) {
      const src = readSurface(rel)
      expect(src, rel).toMatch(/useKittyAsrSession/)
    }
  })
})
