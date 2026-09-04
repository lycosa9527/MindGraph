import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { DEFAULT_V3_RIBBON_TAB, V3_RIBBON_TABS, isV3RibbonTabId } from '@/canvas-v3/v3RibbonTypes'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('mind map V3 chrome (pills collapsed, Word ribbon expanded)', () => {
  it('keeps the original pill toolbar when collapsed', () => {
    const top = readSrc('src/canvas-v3/V3TopToolbar.vue')
    const pills = readSrc('src/canvas-v3/V3CollapsedPills.vue')
    expect(top).toContain('data-testid="mindmap-v3-top-toolbar"')
    expect(top).toContain('v-if="!classic"')
    expect(top).toContain('class="v3-toolbar"')
    expect(top).toContain('<V3CollapsedPills')
    expect(top).toContain('v3-mindmate-btn')
    expect(top).toContain('data-testid="mindmap-v3-ribbon-chevron"')
    expect(pills).toContain('v3-toolbar__row')
    expect(pills).toContain('v3-toolbar__group')
    expect(pills).toContain('canvas.v3.file')
    expect(pills).toContain('canvas.v3.nodes')
    expect(pills).toContain('canvas.v3.tools')
    expect(pills).toContain('v3-tool-btn--export')
    expect(pills).toContain('canvas.v3.exportImage')
    expect(pills).toContain('canvas.v3.saveMg')
    expect(pills).not.toContain('actions.importMg')
    expect(pills).toContain('v3-tool-btn--auto')
    expect(pills).toContain('v3-tool-btn--learn')
    expect(pills).toContain('v3-tool-btn--palette')
    expect(pills).toContain('v3-mindmate-btn')
    expect(pills.indexOf('canvas.v3.tools')).toBeLessThan(pills.indexOf('v3-mindmate-btn'))
  })

  it('shows the five-tab Word ribbon only when expanded', () => {
    const top = readSrc('src/canvas-v3/V3TopToolbar.vue')
    const ribbon = readSrc('src/canvas-v3/V3Ribbon.vue')
    expect(top).toContain('<V3Ribbon')
    expect(ribbon).toContain('data-testid="mindmap-v3-ribbon"')
    expect(ribbon).toContain('role="tablist"')
    expect(ribbon).toContain('mindmap-v3-ribbon-tab-')
    expect(ribbon).toContain('class="v3-ribbon__scroll is-classic"')
    expect([...V3_RIBBON_TABS]).toEqual(['file', 'home', 'design', 'review', 'ai'])
    expect(DEFAULT_V3_RIBBON_TAB).toBe('home')
    expect(isV3RibbonTabId('home')).toBe(true)
    expect(isV3RibbonTabId('palette')).toBe(false)
  })

  it('puts Word Home clipboard first and zoom on the status bar', () => {
    const home = readSrc('src/canvas-v3/V3RibbonHome.vue')
    const group = readSrc('src/canvas-v3/V3RibbonGroup.vue')
    const css = readSrc('src/canvas-v3/v3Ribbon.css')
    const status = readSrc('src/canvas-v3/V3StatusBar.vue')
    const clipboardAt = home.indexOf('group="clipboard"')
    const fontAt = home.indexOf('group="font"')
    expect(clipboardAt).toBeGreaterThan(-1)
    expect(fontAt).toBeGreaterThan(clipboardAt)
    expect(home).toContain('diagram.contextMenu.paste')
    expect(home).toContain('diagram.contextMenu.cut')
    expect(home).toContain('diagram.contextMenu.copy')
    expect(home).toContain('AlignLeft')
    expect(home).toContain('AlignCenter')
    expect(home).toContain('AlignRight')
    expect(home).toContain('variant="icon"')
    expect(group).toContain('v3-ribbon-group__body')
    expect(group).toContain("is-classic': props.classic")
    expect(css).toContain('grid-auto-flow: column')
    expect(css).toContain('overflow-y: hidden')
    expect(status).toContain('data-testid="mindmap-v3-zoom-out"')
    expect(status).toContain('data-testid="mindmap-v3-zoom-in"')
    expect(status).toContain('data-testid="mindmap-v3-zoom-percent"')
    expect(status).toContain('data-testid="mindmap-v3-fit-view"')
    expect(status).toContain('data-testid="mindmap-v3-hand-tool"')
  })

  it('does not persist ribbon height or tab in browser storage', () => {
    const state = readSrc('src/canvas-v3/useV3RibbonState.ts')
    expect(state).toContain('/api/auth/diagram-preferences')
    expect(state).toContain('v3_ribbon_classic')
    expect(state).toContain('v3_ribbon_tab')
    expect(state).not.toContain('localStorage')
    expect(state).not.toContain('sessionStorage')
  })

  it('wires V3 chrome on CanvasPage and keeps the V2 diagram shell', () => {
    const page = readSrc('src/pages/CanvasPage.vue')
    const router = readSrc('src/components/diagram/MindMapCanvasRouter.vue')
    const property = readSrc('src/canvas-v3/V3PropertyPanel.vue')
    expect(page).toContain('<V3TopToolbar')
    expect(page).toContain('v-if="useMindMapV3"')
    expect(page).toContain('<V3StatusBar')
    expect(page).toContain('v-if="useMindMapV3 && showBottomBar"')
    expect(page).toContain('<V3PropertyPanel v-if="useMindMapV3 && !mindClassroomSlideDeck"')
    expect(property).toContain('data-testid="mindmap-v3-property-panel"')
    expect(page).toContain('isMindMapRibbonFamily')
    expect(router).toContain("effectiveMode === 'legacy'")
    expect(router).toContain(':key="\'mindmap-v2\'"')
    expect(router).not.toContain('MindMapV3Canvas')
  })
})
