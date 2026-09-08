import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { DEFAULT_MIND_MAP_RIBBON_TAB, MIND_MAP_RIBBON_TABS, isMindMapRibbonTabId } from '@/canvas-ribbon/mindMapRibbonTypes'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('mind map ribbon chrome (V2 title row + status bar)', () => {
  it('shows File/Edit/Draw/Teaching/Research tabs on the title row', () => {
    const topBar = readSrc('src/components/canvas/CanvasTopBar.vue')
    const tabs = readSrc('src/canvas-ribbon/MindMapRibbonTabs.vue')
    expect(topBar).toContain('<MindMapRibbonTabs')
    expect(tabs).toContain('mm-ribbon-tabs--topbar')
    expect(tabs).toContain('role="tablist"')
    expect(tabs).toContain('mindmap-ribbon-tab-')
    expect([...MIND_MAP_RIBBON_TABS]).toEqual(['file', 'edit', 'ai', 'teaching', 'research'])
    expect(DEFAULT_MIND_MAP_RIBBON_TAB).toBe('edit')
    expect(isMindMapRibbonTabId('ai')).toBe(true)
    expect(isMindMapRibbonTabId('draw')).toBe(false)
    expect(isMindMapRibbonTabId('learn')).toBe(false)
    expect(isMindMapRibbonTabId('palette')).toBe(false)
  })

  it('puts zoom on the status bar', () => {
    const status = readSrc('src/canvas-ribbon/MindMapStatusBar.vue')
    const css = readSrc('src/canvas-ribbon/mindMapRibbon.css')
    const chrome = readSrc('src/canvas-ribbon/mindMapStatusBar.css')
    expect(status).toContain('data-testid="mindmap-ribbon-zoom-out"')
    expect(status).toContain('data-testid="mindmap-ribbon-zoom-in"')
    expect(status).toContain('data-testid="mindmap-ribbon-zoom-percent"')
    expect(status).toContain('data-testid="mindmap-ribbon-fit-view"')
    expect(status).toContain('data-testid="mindmap-ribbon-hand-tool"')
    expect(chrome).toMatch(/\.mm-status\s*\{[\s\S]*?display:\s*flex/)
    expect(chrome).toContain('flex-wrap: nowrap')
    expect(chrome).toContain('max-height: 40px')
    expect(css).toContain('.mm-status__zoom-btn')
    expect(css).toMatch(/\.mm-status__zoom-btn\s*\{[\s\S]*?height:\s*28px/)
  })

  it('does not persist ribbon height or tab in browser storage', () => {
    const state = readSrc('src/canvas-ribbon/useMindMapRibbonState.ts')
    expect(state).toContain('/api/auth/diagram-preferences')
    expect(state).toContain('v3_ribbon_classic')
    expect(state).toContain('v3_ribbon_tab')
    expect(state).not.toContain('localStorage')
    expect(state).not.toContain('sessionStorage')
  })

  it('puts collaborative drawing on the title row as a global control', () => {
    const topBar = readSrc('src/components/canvas/CanvasTopBar.vue')
    const mmToolbar = readSrc('src/components/canvas/CanvasToolbarMindMap.vue')
    expect(topBar).toContain('canvas-top-bar__global')
    expect(topBar).toContain('<CanvasOnlineCollabMenu')
    expect(mmToolbar).not.toContain("openCollab('organization')")
  })

  it('uses V2 chrome on CanvasPage and keeps the V2 diagram shell', () => {
    const page = readSrc('src/pages/CanvasPage.vue')
    const router = readSrc('src/components/diagram/MindMapCanvasRouter.vue')
    expect(page).not.toContain('V3TopToolbar')
    expect(page).not.toContain('V3PropertyPanel')
    expect(page).not.toContain('useMindMapV3')
    expect(page).toContain('useMindMapV2Chrome')
    expect(page).toContain('<MindMapStatusBar')
    expect(page).toContain('v-if="isMindMapRibbonFamily && showBottomBar"')
    expect(page).toContain('isMindMapRibbonFamily')
    expect(router).toContain("effectiveMode === 'legacy'")
    expect(router).toContain(':key="\'mindmap-v2\'"')
    expect(router).not.toContain('MindMapV3Canvas')
  })
})
