import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const modalPath = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../src/components/settings/LanguageSettingsModal.vue'
)

describe('Language settings canvas segmented control', () => {
  it('exposes V1 V2 and V3 segments when the V3 flag is on', () => {
    const source = readFileSync(modalPath, 'utf8')
    expect(source).toContain("t('settings.language.mindMapCanvasV1')")
    expect(source).toContain("t('settings.language.mindMapCanvasV2')")
    expect(source).toContain("t('settings.language.mindMapCanvasV3')")
    expect(source).toContain('data-testid="mindmap-canvas-v3-segment"')
    expect(source).toContain('v-if="featureMindmapV3Canvas"')
    expect(source).toContain("draftMindMapCanvasMode = 'v3'")
  })
})
