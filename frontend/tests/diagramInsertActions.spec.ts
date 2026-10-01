import { describe, expect, it } from 'vitest'

import { diagramInsertActions } from '@/canvas-ribbon/diagramInsertActions'

describe('diagramInsertActions', () => {
  it('keeps child and sibling on a mind map', () => {
    expect(diagramInsertActions('mindmap').map((action) => action.id)).toEqual(['child', 'sibling'])
  })

  it('uses the classic add for each thinking map', () => {
    expect(diagramInsertActions('concept_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('concept_map').map((action) => action.labelKey)).toEqual([
      'canvas.toolbar.addNode',
    ])
    expect(diagramInsertActions('circle_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('bubble_map').map((action) => action.labelKey)).toEqual([
      'canvas.toolbar.addNode',
    ])
    expect(diagramInsertActions('tree_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('flow_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('brace_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('double_bubble_map').map((action) => action.id)).toEqual(['node'])
    expect(diagramInsertActions('multi_flow_map').map((action) => action.id)).toEqual([
      'cause',
      'effect',
    ])
    expect(diagramInsertActions('bridge_map').map((action) => action.labelKey)).toEqual([
      'canvas.toolbar.addAnalogyPair',
    ])
  })
})
