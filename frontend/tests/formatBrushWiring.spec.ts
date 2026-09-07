import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function readSrc(rel: string): string {
  return readFileSync(resolve(root, rel), 'utf8')
}

describe('format painter wiring', () => {
  it('double-click locks the painter on the mind-map edit toolbar', () => {
    const toolbar = readSrc('src/components/canvas/CanvasToolbarMindMap.vue')
    expect(toolbar).toContain('onFormatPainterDblClick')
    expect(toolbar).toContain('handleFormatBrush({ lock: true })')
    expect(toolbar).toContain('@dblclick.prevent="onFormatPainterDblClick"')
    expect(toolbar).toContain("'is-locked': formatBrushLocked")
  })

  it('double-click locks on the format strip, classic toolbar, and V3 home ribbon', () => {
    const format = readSrc('src/components/canvas/CanvasToolbarMindMapFormat.vue')
    const classic = readSrc('src/components/canvas/CanvasToolbar.vue')
    const home = readSrc('src/canvas-v3/V3RibbonHome.vue')
    const command = readSrc('src/canvas-v3/V3RibbonCommand.vue')
    expect(format).toContain("@dblclick.prevent=\"handleFormatBrush({ lock: true })\"")
    expect(classic).toContain("@dblclick.prevent=\"handleFormatBrush({ lock: true })\"")
    expect(home).toContain("@dblclick=\"handleFormatBrush({ lock: true })\"")
    expect(command).toContain("dblclick: []")
    expect(command).toContain("@dblclick.prevent=\"emit('dblclick')\"")
  })

  it('cancels on canvas pane click and shows a copy cursor while active', () => {
    const formatting = readSrc('src/composables/canvasToolbar/useCanvasToolbarFormatting.ts')
    const canvas = readSrc('src/components/diagram/DiagramCanvas.vue')
    expect(formatting).toContain("eventBus.on('canvas:pane_clicked', onFormatBrushPaneClick)")
    expect(formatting).toContain("event.key !== 'Escape'")
    expect(canvas).toContain("'diagram-canvas--format-brush': formatBrushActive")
    expect(canvas).toContain('cursor: copy')
  })
})
