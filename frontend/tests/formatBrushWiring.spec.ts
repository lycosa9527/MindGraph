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

  it('double-click locks on the format strip and classic toolbar', () => {
    const format = readSrc('src/components/canvas/CanvasToolbarMindMapFormat.vue')
    const classic = readSrc('src/components/canvas/CanvasToolbar.vue')
    expect(format).toContain('@dblclick.prevent="handleFormatBrush({ lock: true })"')
    expect(classic).toContain('@dblclick.prevent="handleFormatBrush({ lock: true })"')
    expect(classic).toContain("import { ArrowDownUp, Brush, Upload } from '@lucide/vue'")
  })

  it('cancels on canvas pane click and shows a copy cursor while active', () => {
    const brush = readSrc('src/composables/canvasToolbar/useCanvasFormatBrush.ts')
    const canvas = readSrc('src/components/diagram/DiagramCanvas.vue')
    expect(brush).toContain("eventBus.on('canvas:pane_clicked', onFormatBrushPaneClick)")
    expect(brush).toContain("eventBus.on('canvas:node_clicked', onFormatBrushNodeClicked)")
    expect(brush).toContain("eventBus.on('state:selection_changed', onFormatBrushSelectionChanged)")
    expect(brush).toContain("event.key !== 'Escape'")
    expect(canvas).toContain("'diagram-canvas--format-brush': formatBrushActive")
    expect(canvas).toContain('cursor: copy')
  })

  it('clears the painter when leaving or resetting the canvas', () => {
    const session = readSrc('src/composables/canvasPage/clearCanvasEphemeralSession.ts')
    const brush = readSrc('src/composables/canvasToolbar/useCanvasFormatBrush.ts')
    expect(session).toContain('resetFormatBrushState()')
    expect(brush).toContain("eventBus.on('diagram:loaded', onFormatBrushSessionEnded)")
    expect(brush).toContain("eventBus.on('diagram:type_changed', onFormatBrushSessionEnded)")
  })

  it('paints on new-canvas node click so Vue Flow miss hits still apply', () => {
    const branch = readSrc('src/components/diagram/nodes/mindMap/MindMapV2BranchNode.vue')
    const topic = readSrc('src/components/diagram/nodes/mindMap/MindMapV2TopicNode.vue')
    const handlers = readSrc('src/composables/diagramCanvas/useDiagramCanvasVueFlowHandlers.ts')
    expect(branch).toContain('applyFormatBrushToNode(props.id)')
    expect(topic).toContain('applyFormatBrushToNode(props.id)')
    expect(handlers).toContain("eventBus.emit('canvas:node_clicked'")
  })
})
