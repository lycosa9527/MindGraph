import { describe, expect, it } from 'vitest'

import {
  diagramRibbonCapabilities,
  isDiagramRibbonFamily,
} from '@/canvas-ribbon/diagramRibbonCapabilities'

describe('diagramRibbonCapabilities', () => {
  it('keeps v2-only tools on the mind map', () => {
    const caps = diagramRibbonCapabilities('mindmap', true)
    expect(caps.mindMapTree).toBe(true)
    expect(caps.mindMapV2).toBe(true)
    expect(caps.mindMapFormat).toBe(true)
    expect(caps.explain).toBe(true)
    expect(caps.mindClassroom).toBe(true)
    expect(caps.subgraph).toBe(true)
    expect(caps.docGenerate).toBe(true)
    expect(caps.outline).toBe(true)
    expect(caps.standardExport).toBe(false)
    expect(caps.learningSheetPanel).toBe(true)
    expect(caps.learningSheetToggle).toBe(false)
  })

  it('gives classic mind maps the tree tools without v2 chrome', () => {
    const caps = diagramRibbonCapabilities('mindmap', false)
    expect(caps.mindMapTree).toBe(true)
    expect(caps.mindMapV2).toBe(false)
    expect(caps.subgraph).toBe(false)
    expect(caps.standardExport).toBe(true)
    expect(caps.learningSheetToggle).toBe(true)
  })

  it('keeps thinking-map AI tools and type slots', () => {
    const circle = diagramRibbonCapabilities('circle_map', false)
    expect(circle.mindMapTree).toBe(false)
    expect(circle.mindMapV2).toBe(false)
    expect(circle.waterfall).toBe(true)
    expect(circle.thinkingMapChrome).toBe(true)
    expect(circle.mindMapFormat).toBe(true)
    expect(circle.explain).toBe(true)
    expect(circle.mindClassroom).toBe(true)
    expect(circle.learningSheetPanel).toBe(true)
    expect(circle.learningSheetToggle).toBe(false)
    expect(circle.docGenerate).toBe(false)
    expect(circle.subgraph).toBe(false)
    expect(circle.topicGenerate).toBe(true)
    expect(circle.oneSentence).toBe(true)
    expect(circle.standardExport).toBe(true)
    expect(circle.outline).toBe(true)
    expect(circle.gestureGuide).toBe(true)

    const flow = diagramRibbonCapabilities('flow_map', false)
    expect(flow.flowOrientation).toBe(true)
    expect(flow.subgraph).toBe(false)

    expect(diagramRibbonCapabilities('tree_map', false).subgraph).toBe(true)
    expect(diagramRibbonCapabilities('brace_map', false).subgraph).toBe(true)
    expect(diagramRibbonCapabilities('bubble_map', false).subgraph).toBe(false)
    expect(diagramRibbonCapabilities('double_bubble_map', false).subgraph).toBe(false)
    expect(diagramRibbonCapabilities('multi_flow_map', false).subgraph).toBe(false)
    expect(diagramRibbonCapabilities('bridge_map', false).subgraph).toBe(false)

    const concept = diagramRibbonCapabilities('concept_map', false)
    expect(concept.conceptMap).toBe(true)
    expect(concept.thinkingMapChrome).toBe(false)
    expect(concept.mindMapFormat).toBe(true)
    expect(concept.explain).toBe(true)
    expect(concept.mindClassroom).toBe(true)
    expect(concept.learningSheetPanel).toBe(true)
    expect(concept.learningSheetToggle).toBe(false)
    expect(concept.conceptGenerate).toBe(true)
    expect(concept.docGenerate).toBe(false)
    expect(concept.subgraph).toBe(true)
    expect(concept.outline).toBe(false)
    expect(concept.gestureGuide).toBe(false)
    expect(concept.waterfall).toBe(true)
    expect(concept.oneSentence).toBe(true)
    expect(concept.topicGenerate).toBe(true)
    expect(isDiagramRibbonFamily('concept_map', false)).toBe(true)
    expect(isDiagramRibbonFamily('unknown', false)).toBe(false)
  })
})
