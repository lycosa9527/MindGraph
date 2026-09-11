import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { FIT_PADDING } from '@/config/uiConfig'
import {
  formatFitPaddingPx,
  resolveDiagramFitChromeInsetsPx,
} from '@/utils/mindMapFitChromeInsets'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')

describe('resolveDiagramFitChromeInsetsPx', () => {
  it('uses edge breathing room on the new-canvas ribbon (no left toolbar reserve)', () => {
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: true,
        conceptMap: false,
        treeMapAltDims: false,
        presentationRailVisible: false,
      })
    ).toEqual({
      top: FIT_PADDING.STANDARD_PX,
      right: FIT_PADDING.STANDARD_PX,
      bottom: FIT_PADDING.STANDARD_PX,
      left: FIT_PADDING.STANDARD_PX,
    })
  })

  it('keeps classic overlay chrome (header + floating zoom/AI cluster)', () => {
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: false,
        conceptMap: false,
        treeMapAltDims: false,
        presentationRailVisible: false,
      })
    ).toEqual({
      top: FIT_PADDING.TOP_UI_HEIGHT_PX,
      right: FIT_PADDING.STANDARD_PX,
      bottom: FIT_PADDING.BOTTOM_UI_HEIGHT_PX,
      left: FIT_PADDING.STANDARD_PX,
    })
  })

  it('adds concept-map topic-menu space only on classic chrome', () => {
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: false,
        conceptMap: true,
        treeMapAltDims: false,
        presentationRailVisible: false,
      }).top
    ).toBe(FIT_PADDING.TOP_UI_HEIGHT_PX + FIT_PADDING.MAIN_TOPIC_MENU_ICON_PX)
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: true,
        conceptMap: true,
        treeMapAltDims: false,
        presentationRailVisible: false,
      }).top
    ).toBe(FIT_PADDING.STANDARD_PX)
  })

  it('adds tree-map alternative-dimension space on the bottom', () => {
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: false,
        conceptMap: false,
        treeMapAltDims: true,
        presentationRailVisible: false,
      }).bottom
    ).toBe(
      FIT_PADDING.BOTTOM_UI_HEIGHT_PX + FIT_PADDING.TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX
    )
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: true,
        conceptMap: false,
        treeMapAltDims: true,
        presentationRailVisible: false,
      }).bottom
    ).toBe(FIT_PADDING.STANDARD_PX + FIT_PADDING.TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX)
  })

  it('reserves the presentation rail on the right', () => {
    expect(
      resolveDiagramFitChromeInsetsPx({
        ribbonChrome: true,
        conceptMap: false,
        treeMapAltDims: false,
        presentationRailVisible: true,
      }).right
    ).toBe(FIT_PADDING.PRESENTATION_SIDE_TOOLBAR_RIGHT_PX)
  })
})

describe('formatFitPaddingPx', () => {
  it('formats pixel strings for Vue Flow', () => {
    expect(formatFitPaddingPx(40)).toBe('40px')
  })
})

describe('useDiagramCanvasFit chrome wiring', () => {
  it('uses the chrome-inset helper and does not keep the removed left toolbar reserve', () => {
    const fit = readFileSync(
      resolve(frontendRoot, 'src/composables/diagramCanvas/useDiagramCanvasFit.ts'),
      'utf8'
    )
    expect(fit).toContain('resolveDiagramFitChromeInsetsPx')
    expect(fit).not.toContain('resolveMindMapSideToolbarLeftReservePx')
    expect(fit).not.toContain('isMindMapSideToolbarAffectingFit')
    expect(fit).not.toContain('STANDARD_WITH_BOTTOM_UI')
    expect(fit).not.toContain('MIND_MAP_SIDE_TOOLBAR')
    expect(fit).not.toContain('MIND_MAP_TWO_ROW_CHROME_PX')
  })
})
