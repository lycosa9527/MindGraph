import { describe, expect, it } from 'vitest'

import { isCanvasEditorRibbonFamily } from '@/canvas-ribbon/canvasEditorRibbon'

describe('canvas editor ribbon family', () => {
  it('keeps the ribbon while the diagram type is still unknown', () => {
    expect(isCanvasEditorRibbonFamily(null, 'v2')).toBe(true)
    expect(isCanvasEditorRibbonFamily(undefined, 'legacy')).toBe(true)
    expect(isCanvasEditorRibbonFamily('', 'v2')).toBe(true)
  })

  it('uses the ribbon for mind maps, thinking maps, and concept maps', () => {
    expect(isCanvasEditorRibbonFamily('mindmap', 'legacy')).toBe(true)
    expect(isCanvasEditorRibbonFamily('mind_map', 'v2')).toBe(true)
    expect(isCanvasEditorRibbonFamily('circle_map', 'v2')).toBe(true)
    expect(isCanvasEditorRibbonFamily('concept_map', 'v2')).toBe(true)
  })

  it('keeps the generic diagram type on the ribbon', () => {
    expect(isCanvasEditorRibbonFamily('diagram', 'v2')).toBe(true)
  })
})
