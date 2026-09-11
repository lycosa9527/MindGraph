import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  DEFAULT_MIND_MAP_RIBBON_TAB,
  MIND_MAP_RIBBON_TABS,
  isMindMapRibbonTabId,
  resolveLandingMindMapRibbonTab,
} from '@/canvas-ribbon/mindMapRibbonTypes'

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
    expect(resolveLandingMindMapRibbonTab('file')).toBe('edit')
    expect(resolveLandingMindMapRibbonTab('teaching')).toBe('teaching')
    expect(resolveLandingMindMapRibbonTab(null)).toBe('edit')
    expect(isMindMapRibbonTabId('ai')).toBe(true)
    expect(isMindMapRibbonTabId('draw')).toBe(false)
    expect(isMindMapRibbonTabId('learn')).toBe(false)
    expect(isMindMapRibbonTabId('palette')).toBe(false)
  })

  it('reuses the status-bar translate button for language pick and LLM loading', () => {
    const status = readSrc('src/canvas-ribbon/MindMapStatusBar.vue')
    const picker = readSrc('src/canvas-ribbon/CanvasDiagramTranslateLangPicker.vue')
    const chrome = readSrc('src/canvas-ribbon/mindMapStatusBar.css')
    expect(status).toContain('<CanvasDiagramTranslateLangPicker')
    expect(status).not.toContain('mindmap-ribbon-translate-confirm')
    expect(status).not.toContain('mm-llm-translate-btn')
    expect(picker).toContain('<LlmPhaseRing')
    expect(picker).toContain('is-translating')
    expect(picker).toContain('mindgraph-lang-switcher-popper')
    expect(picker).toContain('getGalleryLanguageMenuRows')
    expect(picker).toContain('armAndStartTranslate')
    expect(picker).toContain('aiBlockedByCollab')
    const chromeActions = readSrc('src/canvas-ribbon/useMindMapRibbonChromeActions.ts')
    expect(chromeActions).toContain('leaveTranslatePreview')
    expect(chromeActions).toContain('switchToModel(model)')
    expect(chrome).toContain('.mm-status__translate-btn.is-translating')
    const toolbarApps = readSrc('src/composables/canvasToolbar/useCanvasToolbarApps.ts')
    expect(toolbarApps).toContain('useMindMapV2.value')
    expect(toolbarApps).toContain("appKey !== 'translate_diagram'")
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

  it('sits the live collab session bar flush against the mind-map toolbar', () => {
    const topBar = readSrc('src/components/canvas/CanvasTopBar.vue')
    expect(topBar).toContain('canvas-top-bar--collab-flush')
    expect(topBar).toContain('Boolean(workshopCode)')
    expect(topBar).toMatch(
      /\.canvas-top-bar--mindmap\.canvas-top-bar--collab-flush\s*\{[\s\S]*?padding-bottom:\s*0/
    )
  })

  it('keeps the session banner school-safe and does not duplicate reconnect chrome', () => {
    const overlay = readSrc('src/components/canvas/CanvasCollabOverlay.vue')
    const rail = readSrc('src/components/canvas/CollabUserRail.vue')
    expect(overlay).toContain("workshopVisibility === 'network'")
    expect(overlay).toContain('data-collab-session-banner')
    expect(overlay).toContain('!props.workshopCode && isReconnecting')
    expect(overlay).not.toContain('isCollabGuest')
    expect(rail).toContain('useCanvasChromeBottomOffset')
    expect(rail).not.toContain('top: 56px')
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
