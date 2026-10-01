import { describe, expect, it } from 'vitest'

import { diagramRibbonCapabilities } from '@/canvas-ribbon/diagramRibbonCapabilities'

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

  it('hides mind-map tools on thinking maps and keeps type slots', () => {
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
    expect(circle.standardExport).toBe(true)

    const flow = diagramRibbonCapabilities('flow_map', false)
    expect(flow.flowOrientation).toBe(true)

    const concept = diagramRibbonCapabilities('concept_map', false)
    expect(concept.conceptMap).toBe(true)
    expect(concept.thinkingMapChrome).toBe(false)
    expect(concept.mindMapFormat).toBe(false)
    expect(concept.explain).toBe(false)
    expect(concept.mindClassroom).toBe(false)
    expect(concept.learningSheetPanel).toBe(false)
    expect(concept.learningSheetToggle).toBe(true)
    expect(concept.conceptGenerate).toBe(true)
    expect(concept.waterfall).toBe(false)
    expect(concept.oneSentence).toBe(true)
    expect(concept.topicGenerate).toBe(true)
  })
})
