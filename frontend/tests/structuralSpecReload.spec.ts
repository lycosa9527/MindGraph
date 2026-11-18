/**
 * A structure edit reloads the current diagram without looking like a new open.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { STRUCTURAL_SPEC_RELOAD } from '@/stores/diagram/types'

describe('structural diagram reloads', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  it('keeps the session, theme, and step style when a flow step is added', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        { title: 'Plan', steps: [{ id: 'step-keep', text: 'Start' }] },
        'flow_map',
        { emitLoaded: false }
      )
    ).toBe(true)
    store.sessionEditCount = 4
    if (store.data) store.data._mindmap_theme = 'ink'
    const step = store.data?.nodes.find((node) => node.id === 'step-keep')
    expect(step).toBeTruthy()
    if (step) step.style = { ...(step.style ?? {}), fontSize: 22 }
    store.layoutMeasureSettling = false

    expect(store.addFlowMapStep('Next')).toBe(true)

    expect(store.sessionEditCount).toBe(4)
    expect(store.layoutMeasureSettling).toBe(false)
    expect(store.data?._mindmap_theme).toBe('ink')
    expect(store.data?.nodes.find((node) => node.id === 'step-keep')?.style?.fontSize).toBe(22)
    expect(store.data?.nodes.some((node) => node.text === 'Next')).toBe(true)
    expect(store.history).toHaveLength(1)
    expect(store.history[0]?.action).toBe('Add flow step')
    expect(store.canUndo).toBe(false)
  })

  it('adds a flow substep under the step it belongs to', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        {
          title: 'Plan',
          steps: [
            { id: 'step-keep', text: 'Start' },
            { id: 'step-next', text: 'Next' },
          ],
        },
        'flow_map',
        { emitLoaded: false }
      )
    ).toBe(true)

    expect(store.addFlowMapSubstep('Start', 'Detail', 0, 'step-keep')).toBe(true)
    expect(store.addFlowMapSubstep('Start', 'Detail 2', 0, 'step-keep')).toBe(true)

    const subs = store.data?.nodes.filter((node) => node.type === 'flowSubstep') ?? []
    expect(subs.map((node) => node.text)).toEqual(['Detail', 'Detail 2'])
    expect(subs.every((node) => node.data?.parentStepId === 'step-keep')).toBe(true)
  })

  it('inserts flow steps before/after and substeps at left/append/right', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        {
          title: 'Plan',
          steps: [
            { id: 'step-a', text: 'A' },
            { id: 'step-b', text: 'B' },
          ],
          substeps: [{ step: 'A', stepId: 'step-a', stepIndex: 0, substeps: ['A1'] }],
        },
        'flow_map',
        { emitLoaded: false }
      )
    ).toBe(true)

    // Topic / event +: insert immediately to the right of the event (index 0).
    expect(store.insertFlowMapStepAt('First', 0)).toBe(true)
    expect(store.data?.nodes.filter((n) => n.type === 'flow').map((n) => n.text)).toEqual([
      'First',
      'A',
      'B',
    ])

    // Step left/right +: predecessor / successor.
    expect(store.insertFlowMapStepAt('Before-B', 2)).toBe(true)
    expect(store.insertFlowMapStepAt('After-B', 4)).toBe(true)
    expect(store.data?.nodes.filter((n) => n.type === 'flow').map((n) => n.text)).toEqual([
      'First',
      'A',
      'Before-B',
      'B',
      'After-B',
    ])

    // Step bottom +: append as rightmost child; substep L/R insert around siblings.
    const stepA = store.data?.nodes.find((n) => n.text === 'A' && n.type === 'flow')
    expect(stepA).toBeTruthy()
    expect(store.insertFlowMapSubstepAt('A', 'A2', undefined, 1, stepA?.id)).toBe(true)
    expect(store.insertFlowMapSubstepAt('A', 'A0', 0, 1, stepA?.id)).toBe(true)
    expect(store.insertFlowMapSubstepAt('A', 'A1b', 2, 1, stepA?.id)).toBe(true)
    const underA =
      store.data?.nodes
        .filter((n) => n.type === 'flowSubstep' && n.data?.parentStepId === stepA?.id)
        .map((n) => n.text) ?? []
    expect(underA).toEqual(['A0', 'A1', 'A1b', 'A2'])
  })

  it('keeps a tree node id, style, and hidden answer across a structural reload', () => {
    const store = useDiagramStore()
    const spec = {
      root: {
        text: 'Topic',
        children: [
          {
            id: 'tree-cat-keep',
            text: 'Cat',
            children: [{ id: 'tree-leaf-keep', text: 'Leaf' }],
          },
        ],
      },
    }
    expect(store.loadFromSpec(spec, 'tree_map', { emitLoaded: false })).toBe(true)
    const category = store.data?.nodes.find((node) => node.id === 'tree-cat-keep')
    expect(category).toBeTruthy()
    if (category) {
      category.style = { fontSize: 18 }
      category.data = { ...(category.data ?? {}), hiddenAnswer: 'secret' }
    }
    store.sessionEditCount = 2
    store.layoutMeasureSettling = false

    expect(
      store.loadFromSpec(
        {
          root: {
            text: 'Topic',
            children: [
              {
                id: 'tree-cat-keep',
                text: 'Cat',
                children: [{ id: 'tree-leaf-keep', text: 'Leaf' }],
              },
              { text: 'New', children: [] },
            ],
          },
        },
        'tree_map',
        STRUCTURAL_SPEC_RELOAD
      )
    ).toBe(true)

    const kept = store.data?.nodes.find((node) => node.id === 'tree-cat-keep')
    expect(kept?.style?.fontSize).toBe(18)
    expect(kept?.data?.hiddenAnswer).toBe('secret')
    expect(store.sessionEditCount).toBe(2)
    expect(store.layoutMeasureSettling).toBe(false)
    expect(store.data?.nodes.some((node) => node.text === 'New')).toBe(true)
  })

  it('resets the session when a diagram is opened', () => {
    const store = useDiagramStore()
    store.loadFromSpec({ title: 'Plan', steps: ['Start'] }, 'flow_map', { emitLoaded: false })
    store.sessionEditCount = 4
    store.loadFromSpec({ title: 'Other', steps: ['A'] }, 'flow_map', { emitLoaded: false })
    expect(store.sessionEditCount).toBe(0)
  })

  it('keeps flow step and substep paint across add and connector stroke after border paint', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        {
          title: 'Plan',
          steps: [
            { id: 'step-a', text: 'A' },
            { id: 'step-b', text: 'B' },
          ],
          substeps: [{ step: 'A', stepId: 'step-a', stepIndex: 0, substeps: ['A1'] }],
        },
        'flow_map',
        { emitLoaded: false }
      )
    ).toBe(true)

    const stepA = store.data?.nodes.find((node) => node.id === 'step-a')
    const subA1 = store.data?.nodes.find(
      (node) => node.type === 'flowSubstep' && node.data?.parentStepId === 'step-a'
    )
    expect(stepA && subA1).toBeTruthy()
    if (stepA) {
      stepA.style = {
        ...(stepA.style ?? {}),
        backgroundColor: '#112233',
        borderColor: '#445566',
        textColor: '#ffffff',
        fontSize: 20,
        fontWeight: 'bold',
        nodeShape: 'rounded',
        // Layout leftovers must not be treated as format paint after reload.
        width: 480,
        minWidth: 480,
      }
    }
    if (subA1) {
      subA1.style = {
        ...(subA1.style ?? {}),
        backgroundColor: '#ffeedd',
        borderColor: '#ccaa88',
        fontStyle: 'italic',
      }
    }
    const edge = store.data?.connections?.find(
      (conn) => conn.source === 'step-a' && conn.target === subA1?.id
    )
    if (edge) edge.style = { ...(edge.style ?? {}), strokeColor: '#445566' }

    expect(store.addFlowMapStep('Next')).toBe(true)

    const keptStep = store.data?.nodes.find((node) => node.id === 'step-a')
    const keptSub = store.data?.nodes.find((node) => node.id === subA1?.id)
    expect(keptStep?.style?.backgroundColor).toBe('#112233')
    expect(keptStep?.style?.borderColor).toBe('#445566')
    expect(keptStep?.style?.textColor).toBe('#ffffff')
    expect(keptStep?.style?.fontSize).toBe(20)
    expect(keptStep?.style?.fontWeight).toBe('bold')
    expect(keptStep?.style?.nodeShape).toBe('rounded')
    // Fresh layout may restamp stretch width; the pre-reload 480 leftover must not stick.
    expect(keptStep?.style?.width).not.toBe(480)
    expect(keptStep?.style?.minWidth).not.toBe(480)
    expect(keptSub?.style?.backgroundColor).toBe('#ffeedd')
    expect(keptSub?.style?.borderColor).toBe('#ccaa88')
    expect(keptSub?.style?.fontStyle).toBe('italic')
    const keptEdge = store.data?.connections?.find(
      (conn) => conn.source === 'step-a' && conn.target === keptSub?.id
    )
    expect(keptEdge?.style?.strokeColor).toBe('#445566')
  })

  it('keeps double-bubble difference paint and connector stroke across structural reload', () => {
    const store = useDiagramStore()
    expect(
      store.loadFromSpec(
        {
          left: 'A',
          right: 'B',
          similarities: [{ id: 'sim-1', text: 'Both' }],
          leftDifferences: [{ id: 'ld-1', text: 'Only A' }],
          rightDifferences: [{ id: 'rd-1', text: 'Only B' }],
        },
        'double_bubble_map',
        { emitLoaded: false }
      )
    ).toBe(true)

    const leftDiff = store.data?.nodes.find((node) => node.id === 'ld-1')
    expect(leftDiff).toBeTruthy()
    if (leftDiff) {
      leftDiff.style = {
        ...(leftDiff.style ?? {}),
        backgroundColor: '#ff00aa',
        borderColor: '#880066',
        fontSize: 22,
        borderWidth: 3,
      }
    }
    const edgeToDiff = store.data?.connections?.find(
      (conn) => conn.source === 'left-topic' && conn.target === 'ld-1'
    )
    expect(edgeToDiff).toBeTruthy()
    if (edgeToDiff) {
      edgeToDiff.style = { ...(edgeToDiff.style ?? {}), strokeColor: '#880066' }
    }

    expect(store.updateNode('ld-1', { style: { fontWeight: 'bold' } })).toBe(true)

    const spec = store.getDoubleBubbleSpecFromData()
    expect(spec).toBeTruthy()
    if (!spec) return
    expect(store.loadFromSpec(spec, 'double_bubble_map', STRUCTURAL_SPEC_RELOAD)).toBe(true)

    const kept = store.data?.nodes.find((node) => node.id === 'ld-1')
    expect(kept?.style?.backgroundColor).toBe('#ff00aa')
    expect(kept?.style?.borderColor).toBe('#880066')
    expect(kept?.style?.fontSize).toBe(22)
    expect(kept?.style?.borderWidth).toBe(3)
    expect(kept?.style?.fontWeight).toBe('bold')
    const keptEdge = store.data?.connections?.find(
      (conn) => conn.source === 'left-topic' && conn.target === 'ld-1'
    )
    expect(keptEdge?.style?.strokeColor).toBe('#880066')
  })
})
