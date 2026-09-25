import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  QUICK_ACCESS_DEFAULT_HEIGHT_PX,
  QUICK_ACCESS_DEFAULT_WIDTH_PX,
  QUICK_ACCESS_MIN_HEIGHT_PX,
  QUICK_ACCESS_MIN_WIDTH_PX,
  clampQuickAccessFrame,
  defaultQuickAccessRemoteFrame,
  nextQuickAccessPromptOverrides,
  parseQuickAccessPromptOverrides,
  parseQuickAccessRemotePersisted,
  quickAccessReplaceNeedsConfirm,
  resizeQuickAccessFrame,
  resolveQuickAccessDiagramOpen,
  resolveQuickAccessPromptText,
} from '@/composables/sidebar/quickAccessRemoteModel'
import {
  LANDING_PROMPT_EXAMPLE_KEYS,
  advancedDiagramCards,
  eightThinkingMapCards,
  quickAccessDiagramCards,
} from '@/config/landingQuickAccess'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('quick access remote', () => {
  it('lists the ten landing diagrams in gallery order', () => {
    expect(eightThinkingMapCards).toHaveLength(8)
    expect(advancedDiagramCards.map((card) => card.type)).toEqual(['mindmap', 'concept_map'])
    expect(quickAccessDiagramCards.map((card) => card.type)).toEqual([
      'circle_map',
      'bubble_map',
      'double_bubble_map',
      'tree_map',
      'brace_map',
      'flow_map',
      'multi_flow_map',
      'bridge_map',
      'mindmap',
      'concept_map',
    ])
    expect(readSrc('src/components/mindgraph/InternationalLanding.vue')).toContain(
      'eightThinkingMapCards'
    )
    expect(readSrc('src/components/mindgraph/InternationalLanding.vue')).toContain(
      'advancedDiagramCards'
    )
  })

  it('reuses the six landing preset prompts', () => {
    expect([...LANDING_PROMPT_EXAMPLE_KEYS]).toEqual([
      'landing.international.example1',
      'landing.international.example2',
      'landing.international.example3',
      'landing.international.example4',
      'landing.international.example5',
      'landing.international.example6',
    ])
    const landing = readSrc('src/components/mindgraph/InternationalLanding.vue')
    expect(landing).toContain('executeLandingPrompt')
    expect(landing).toContain('LANDING_PROMPT_EXAMPLE_KEYS')
  })

  it('pushes a new canvas, replaces an open one, and reloads the same blank type', () => {
    expect(
      resolveQuickAccessDiagramOpen({
        onCanvas: false,
        blankTypeQuery: null,
        targetType: 'bubble_map',
      })
    ).toBe('push')
    expect(
      resolveQuickAccessDiagramOpen({
        onCanvas: true,
        blankTypeQuery: null,
        targetType: 'bubble_map',
      })
    ).toBe('replace')
    expect(
      resolveQuickAccessDiagramOpen({
        onCanvas: true,
        blankTypeQuery: 'circle_map',
        targetType: 'tree_map',
      })
    ).toBe('replace')
    expect(
      resolveQuickAccessDiagramOpen({
        onCanvas: true,
        blankTypeQuery: 'flow_map',
        targetType: 'flow_map',
      })
    ).toBe('reload')
    expect(quickAccessReplaceNeedsConfirm(false, true)).toBe(false)
    expect(quickAccessReplaceNeedsConfirm(true, false)).toBe(false)
    expect(quickAccessReplaceNeedsConfirm(true, true)).toBe(true)
  })

  it('clamps size to the minimum and the viewport, and restores persisted width and height', () => {
    const grown = resizeQuickAccessFrame(40, 40, 20, 20, 1280, 800)
    expect(grown).toEqual({
      width: QUICK_ACCESS_MIN_WIDTH_PX,
      height: QUICK_ACCESS_MIN_HEIGHT_PX,
    })
    const capped = resizeQuickAccessFrame(1000, 40, 900, QUICK_ACCESS_DEFAULT_HEIGHT_PX, 1280, 800)
    expect(capped.width).toBe(1280 - 1000 - 16)
    expect(capped.height).toBe(QUICK_ACCESS_DEFAULT_HEIGHT_PX)

    const shrunk = clampQuickAccessFrame(
      { left: 1100, top: 700, width: 400, height: 500 },
      1280,
      800
    )
    expect(shrunk.left + shrunk.width).toBeLessThanOrEqual(1280 - 8)
    expect(shrunk.top + shrunk.height).toBeLessThanOrEqual(800 - 8)
    expect(shrunk.width).toBeGreaterThan(0)
    expect(shrunk.height).toBeGreaterThan(0)

    const parsed = parseQuickAccessRemotePersisted(
      JSON.stringify({
        left: 12,
        top: 24,
        width: 360,
        height: 480,
        hidden: false,
        tab: 'prompts',
      })
    )
    expect(parsed).toEqual({
      left: 12,
      top: 24,
      width: 360,
      height: 480,
      hidden: false,
      tab: 'prompts',
    })
    const fallback = defaultQuickAccessRemoteFrame(1440, 900)
    expect(fallback.width).toBe(QUICK_ACCESS_DEFAULT_WIDTH_PX)
    expect(fallback.height).toBe(QUICK_ACCESS_DEFAULT_HEIGHT_PX)
  })

  it('saves an edited inspiration prompt and restores the preset when cleared', () => {
    const parsed = parseQuickAccessPromptOverrides(
      JSON.stringify({
        'landing.international.example1': '  photosynthesis map  ',
        'landing.international.example2': '   ',
        other: 'skip',
      }),
      10000
    )
    expect(parsed).toEqual({
      'landing.international.example1': 'photosynthesis map',
    })
    const saved = nextQuickAccessPromptOverrides(
      {},
      'landing.international.example1',
      ' custom prompt ',
      '生成一张关于「光合作用」的思维导图',
      10000
    )
    expect(saved['landing.international.example1']).toBe('custom prompt')
    expect(resolveQuickAccessPromptText('landing.international.example1', 'preset', saved)).toBe(
      'custom prompt'
    )
    const cleared = nextQuickAccessPromptOverrides(
      saved,
      'landing.international.example1',
      'preset',
      'preset',
      10000
    )
    expect(cleared['landing.international.example1']).toBeUndefined()
    expect(resolveQuickAccessPromptText('landing.international.example1', 'preset', cleared)).toBe(
      'preset'
    )
  })

  it('is opened from both account menus and mounted on the app shell', () => {
    const footer = readSrc('src/components/sidebar/AppSidebarAccountFooter.vue')
    const app = readSrc('src/App.vue')
    const remote = readSrc('src/components/sidebar/QuickAccessRemote.vue')
    expect(footer.match(/sidebar\.quickAccessRemote/g)).toHaveLength(2)
    expect(footer).toContain('<el-dropdown-item @click="toggleQuickAccessRemote">')
    expect(footer).toContain('menuOnly')
    expect(app).toContain('<QuickAccessRemote')
    expect(app).toContain('quickAccessRemoteHidden')
    expect(app).toContain('showFloatingAccountMenu')
    expect(readSrc('src/components/sidebar/FloatingAccountMenu.vue')).toContain('menu-only')
    expect(readSrc('src/layouts/DefaultLayout.vue')).toContain('toggleQuickAccessRemote')
    expect(readSrc('src/components/workshop-chat/WorkshopPersonalMenu.vue')).toContain(
      'toggleQuickAccessRemote'
    )
    expect(remote).toContain('data-testid="quick-access-remote-resize"')
    expect(remote).toContain('executeLandingPrompt')
    expect(remote).toContain('quick-access-diagram-')
    expect(remote).toContain('DiagramPreviewSvg')
    expect(remote).toContain('@contextmenu="beginPromptEdit(key, $event)"')
    expect(remote).toContain('commitQuickAccessPromptEdit')
    expect(remote).toContain('LlmPhaseRing')
    expect(remote).toContain('runningPromptKey')
    expect(remote).toContain('cancelInFlightGeneration')
    expect(remote).toContain('clearPromptRun')
    const remoteCss = readSrc('src/components/sidebar/quickAccessRemote.css')
    expect(remoteCss).toContain('qa-prompt-travel')
    expect(remoteCss).toContain('repeat(2, minmax(0, 1fr))')
    expect(remoteCss).toContain('repeat(5, minmax(3.4rem, 1fr))')
    expect(remoteCss).toContain('auto-fit')
  })
})
