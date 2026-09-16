import { describe, expect, it } from 'vitest'

import { loadFlowMapSpec, recalculateFlowMapLayout } from '@/stores/specLoader/flowMap'
import {
  collectFlowMapSpecFromNodes,
  findFlowSubstepEntry,
  flowStepIndexFromNodeId,
  resolveFlowMapOrientation,
  resolveFlowSubstepsForSteps,
  swapFlowMapCollectedSteps,
} from '@/stores/specLoader/flowMapSubsteps'

describe('flowMapSubsteps', () => {
  it('collects substeps per step index when labels collide', () => {
    const spec = collectFlowMapSpecFromNodes([
      { id: 'flow-topic', type: 'topic', text: 'Process' },
      { id: 'flow-step-0', type: 'flow', text: '新步骤' },
      { id: 'flow-step-1', type: 'flow', text: '新步骤' },
      { id: 'flow-substep-0-0', type: 'flowSubstep', text: 'A1' },
      { id: 'flow-substep-0-1', type: 'flowSubstep', text: 'A2' },
      { id: 'flow-substep-1-0', type: 'flowSubstep', text: 'B1' },
    ])

    expect(spec.steps).toEqual([
      { id: 'flow-step-0', text: '新步骤' },
      { id: 'flow-step-1', text: '新步骤' },
    ])
    expect(spec.substeps).toEqual([
      {
        step: '新步骤',
        stepId: 'flow-step-0',
        stepIndex: 0,
        substeps: [
          { id: 'flow-substep-0-0', text: 'A1' },
          { id: 'flow-substep-0-1', text: 'A2' },
        ],
      },
      {
        step: '新步骤',
        stepId: 'flow-step-1',
        stepIndex: 1,
        substeps: [{ id: 'flow-substep-1-0', text: 'B1' }],
      },
    ])
  })

  it('swaps step objects without detaching UUID child lists', () => {
    const steps: Array<{ id: string; text: string }> = [
      { id: 'step-a', text: 'First' },
      { id: 'step-b', text: 'Second' },
    ]
    const substeps = [
      { step: 'First', stepId: 'step-a', stepIndex: 0, substeps: [{ id: 'a0', text: 'A1' }] },
      { step: 'Second', stepId: 'step-b', stepIndex: 1, substeps: [{ id: 'b0', text: 'B1' }] },
    ]
    swapFlowMapCollectedSteps(steps, substeps, 0, 1)

    expect(steps.map((step) => step.id)).toEqual(['step-b', 'step-a'])
    expect(substeps[0]?.stepId).toBe('step-a')
    expect(substeps[0]?.stepIndex).toBe(1)
    expect(substeps[0]?.substeps).toEqual([{ id: 'a0', text: 'A1' }])
    expect(substeps[1]?.stepId).toBe('step-b')
    expect(substeps[1]?.stepIndex).toBe(0)

    const lists = resolveFlowSubstepsForSteps(steps, substeps)
    expect(lists[0].map((item) => item.text)).toEqual(['B1'])
    expect(lists[1].map((item) => item.text)).toEqual(['A1'])
  })

  it('prefers stepId over colliding labels when resolving substeps', () => {
    const lists = resolveFlowSubstepsForSteps(
      [
        { id: 'step-a', text: '新步骤' },
        { id: 'step-b', text: '新步骤' },
      ],
      [
        { step: '新步骤', stepId: 'step-b', substeps: ['B1'] },
        { step: '新步骤', stepId: 'step-a', substeps: ['A1', 'A2'] },
      ]
    )

    expect(lists[0].map((item) => item.text)).toEqual(['A1', 'A2'])
    expect(lists[1].map((item) => item.text)).toEqual(['B1'])
  })

  it('does not fan one text-keyed list onto every same-named step', () => {
    const lists = resolveFlowSubstepsForSteps(
      [{ text: '新步骤' }, { text: '新步骤' }, { text: 'Unique' }],
      [
        { step: '新步骤', stepIndex: 0, substeps: ['A1', 'A2', 'A3'] },
        { step: '新步骤', stepIndex: 1, substeps: ['B1'] },
        { step: 'Unique', substeps: ['C1', 'C2'] },
      ]
    )

    expect(lists[0].map((item) => item.text)).toEqual(['A1', 'A2', 'A3'])
    expect(lists[1].map((item) => item.text)).toEqual(['B1'])
    expect(lists[2].map((item) => item.text)).toEqual(['C1', 'C2'])
  })

  it('falls back to one unused text match when stepIndex is absent', () => {
    const lists = resolveFlowSubstepsForSteps(
      [{ text: 'Prepare' }, { text: 'Prepare' }],
      [
        { step: 'Prepare', substeps: ['first'] },
        { step: 'Prepare', substeps: ['second'] },
      ]
    )

    expect(lists[0].map((item) => item.text)).toEqual(['first'])
    expect(lists[1].map((item) => item.text)).toEqual(['second'])
  })

  it('finds the entry for the selected step index, not the first same label', () => {
    const entries = [
      { step: '新步骤', stepIndex: 0, substeps: ['A'] },
      { step: '新步骤', stepIndex: 1, substeps: ['B'] },
    ]
    expect(findFlowSubstepEntry(entries, '新步骤', 1)?.substeps).toEqual(['B'])
    expect(flowStepIndexFromNodeId('flow-substep-1-0')).toBe(1)
    expect(flowStepIndexFromNodeId('flow-step-2')).toBe(2)
  })

  it('loadFlowMapSpec keeps duplicate-label steps on their own substep lists', () => {
    const loaded = loadFlowMapSpec({
      title: 'Process',
      steps: ['新步骤', '新步骤'],
      substeps: [
        { step: '新步骤', stepIndex: 0, substeps: ['A1', 'A2'] },
        { step: '新步骤', stepIndex: 1, substeps: ['B1'] },
      ],
      orientation: 'horizontal',
    })

    const steps = loaded.nodes.filter((node) => node.type === 'flow')
    const subs = loaded.nodes.filter((node) => node.type === 'flowSubstep')
    expect(steps.map((node) => node.text)).toEqual(['新步骤', '新步骤'])
    expect(subs.map((node) => node.text)).toEqual(['A1', 'A2', 'B1'])
    expect(subs[0]?.data?.parentStepId).toBe(steps[0]?.id)
    expect(subs[1]?.data?.parentStepId).toBe(steps[0]?.id)
    expect(subs[2]?.data?.parentStepId).toBe(steps[1]?.id)
    for (const node of [...steps, ...subs]) {
      expect(node.id).not.toMatch(/^flow-step-\d+$/)
      expect(node.id).not.toMatch(/^flow-substep-\d+-\d+$/)
    }
  })
})

const PILL = { width: 120, height: 48 }

function flowDims(ids: string[]): Record<string, { width: number; height: number }> {
  return Object.fromEntries(ids.map((id) => [id, PILL]))
}

describe('recalculateFlowMapLayout', () => {
  it('keeps vertical substeps on their step id when Y order is inverted', () => {
    const nodes = [
      {
        id: 'flow-topic',
        text: 'Process',
        type: 'topic' as const,
        position: { x: 100, y: 40 },
        data: { orientation: 'vertical' },
      },
      {
        id: 'flow-step-1',
        text: 'Second',
        type: 'flow' as const,
        position: { x: 200, y: 80 },
        data: { groupIndex: 1 },
      },
      {
        id: 'flow-step-0',
        text: 'First',
        type: 'flow' as const,
        position: { x: 200, y: 400 },
        data: { groupIndex: 0 },
      },
      {
        id: 'flow-substep-0-0',
        text: 'A1',
        type: 'flowSubstep' as const,
        position: { x: 360, y: 400 },
        data: { groupIndex: 0 },
      },
      {
        id: 'flow-substep-1-0',
        text: 'B1',
        type: 'flowSubstep' as const,
        position: { x: 360, y: 80 },
        data: { groupIndex: 1 },
      },
    ]
    const laidOut = recalculateFlowMapLayout(nodes, flowDims(nodes.map((node) => node.id)))
    const byId = Object.fromEntries(laidOut.map((node) => [node.id, node]))
    const step0Y = byId['flow-step-0'].position?.y ?? 0
    const step1Y = byId['flow-step-1'].position?.y ?? 0
    const sub0Y = byId['flow-substep-0-0'].position?.y ?? 0
    const sub1Y = byId['flow-substep-1-0'].position?.y ?? 0
    expect(step0Y).toBeLessThan(step1Y)
    expect(Math.abs(sub0Y - step0Y)).toBeLessThan(Math.abs(sub0Y - step1Y))
    expect(Math.abs(sub1Y - step1Y)).toBeLessThan(Math.abs(sub1Y - step0Y))
  })

  it('matches horizontal substeps by step id when groupIndex is missing', () => {
    const nodes = [
      {
        id: 'flow-topic',
        text: 'Process',
        type: 'topic' as const,
        position: { x: 40, y: 276 },
        data: { orientation: 'horizontal' },
      },
      {
        id: 'flow-step-0',
        text: 'First',
        type: 'flow' as const,
        position: { x: 220, y: 276 },
      },
      {
        id: 'flow-step-1',
        text: 'Second',
        type: 'flow' as const,
        position: { x: 400, y: 276 },
      },
      {
        id: 'flow-substep-0-0',
        text: 'A1',
        type: 'flowSubstep' as const,
        position: { x: 220, y: 360 },
      },
      {
        id: 'flow-substep-1-0',
        text: 'B1',
        type: 'flowSubstep' as const,
        position: { x: 400, y: 360 },
      },
    ]
    const laidOut = recalculateFlowMapLayout(nodes, flowDims(nodes.map((node) => node.id)))
    const byId = Object.fromEntries(laidOut.map((node) => [node.id, node]))
    const step0X = byId['flow-step-0'].position?.x ?? 0
    const step1X = byId['flow-step-1'].position?.x ?? 0
    const sub0X = byId['flow-substep-0-0'].position?.x ?? 0
    const sub1X = byId['flow-substep-1-0'].position?.x ?? 0
    expect(step0X).toBeLessThan(step1X)
    expect(Math.abs(sub0X - step0X)).toBeLessThan(Math.abs(sub0X - step1X))
    expect(Math.abs(sub1X - step1X)).toBeLessThan(Math.abs(sub1X - step0X))
  })

  it('infers vertical orientation from step positions when topic data is missing', () => {
    expect(
      resolveFlowMapOrientation({ data: {} }, [
        { position: { x: 200, y: 80 } },
        { position: { x: 200, y: 220 } },
      ])
    ).toBe('vertical')
    expect(
      resolveFlowMapOrientation({ data: {} }, [
        { position: { x: 200, y: 280 } },
        { position: { x: 400, y: 280 } },
      ])
    ).toBe('horizontal')
  })
})
