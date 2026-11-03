import { describe, expect, it } from 'vitest'

import { FLOW_MAP_ROW_GAP } from '@/composables/diagrams/layoutConfig'
import { loadFlowMapSpec, recalculateFlowMapLayout } from '@/stores/specLoader/flowMap'
import { flowStepSlot } from '@/stores/specLoader/flowMapSerpentine'
import type { DiagramNode } from '@/types'
import { measureFlowRolePill } from '@/utils/flowPillBox'

function stepNodes(nodes: DiagramNode[]): DiagramNode[] {
  return nodes.filter((node) => node.type === 'flow')
}

function byText(nodes: DiagramNode[], text: string): DiagramNode {
  const found = nodes.find((node) => node.text === text)
  if (!found?.position) throw new Error(`missing ${text}`)
  return found
}

function stepCenterX(node: DiagramNode): number {
  const box = measureFlowRolePill(node.text ?? '', 'step')
  return (node.position?.x ?? 0) + box.boxWidth / 2
}

describe('flow map serpentine', () => {
  it('keeps five steps on one row', () => {
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'horizontal',
      steps: ['A', 'B', 'C', 'D', 'E'],
    })
    const steps = stepNodes(loaded.nodes)
    const ys = steps.map((step) => step.position?.y ?? 0)
    expect(new Set(ys).size).toBe(1)
    const xs = steps.map((step) => step.position?.x ?? 0)
    expect(xs).toEqual([...xs].sort((left, right) => left - right))
    const turn = loaded.connections.find((edge) => edge.sourceHandle === 'bottom')
    expect(turn).toBeUndefined()
  })

  it('U-turns the sixth step under the fifth and walks back', () => {
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'horizontal',
      steps: ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
    })
    const fifth = byText(loaded.nodes, 'E')
    const sixth = byText(loaded.nodes, 'F')
    const seventh = byText(loaded.nodes, 'G')
    expect(sixth.position?.y ?? 0).toBeGreaterThan(fifth.position?.y ?? 0)
    expect(Math.abs(stepCenterX(sixth) - stepCenterX(fifth))).toBeLessThan(1)
    expect(seventh.position?.y).toBe(sixth.position?.y)
    expect(seventh.position?.x ?? 0).toBeLessThan(sixth.position?.x ?? 0)

    const down = loaded.connections.find((edge) => edge.target === sixth.id)
    expect(down?.sourceHandle).toBe('right')
    expect(down?.targetHandle).toBe('right-target')
    const back = loaded.connections.find((edge) => edge.target === seventh.id)
    expect(back?.sourceHandle).toBe('left-source')
    expect(back?.targetHandle).toBe('right-target')
  })

  it('turns again on the left after the tenth step', () => {
    expect(flowStepSlot(9)).toEqual({ row: 1, column: 0, direction: 'rtl' })
    expect(flowStepSlot(10)).toEqual({ row: 2, column: 0, direction: 'ltr' })
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'horizontal',
      steps: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11'],
    })
    const tenth = byText(loaded.nodes, '10')
    const eleventh = byText(loaded.nodes, '11')
    expect(eleventh.position?.y ?? 0).toBeGreaterThan(tenth.position?.y ?? 0)
    expect(Math.abs(stepCenterX(eleventh) - stepCenterX(tenth))).toBeLessThan(1)
    const down = loaded.connections.find((edge) => edge.target === eleventh.id)
    expect(down?.sourcePosition).toBe('left')
    expect(down?.targetPosition).toBe('left')
  })

  it('clears substeps before the next row starts', () => {
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'horizontal',
      steps: ['A', 'B', 'C', 'D', 'E', 'F'],
      substeps: [{ step: 'E', substeps: ['note'] }],
    })
    const fifth = byText(loaded.nodes, 'E')
    const note = byText(loaded.nodes, 'note')
    const sixth = byText(loaded.nodes, 'F')
    expect(note.position?.y ?? 0).toBeGreaterThan(fifth.position?.y ?? 0)
    expect(sixth.position?.y ?? 0).toBeGreaterThanOrEqual(
      (note.position?.y ?? 0) + FLOW_MAP_ROW_GAP
    )
  })

  it('keeps a vertical flow in one column', () => {
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'vertical',
      steps: ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
    })
    const xs = stepNodes(loaded.nodes).map((step) => step.position?.x ?? 0)
    expect(new Set(xs).size).toBe(1)
    const down = loaded.connections.find((edge) => edge.sourceHandle === 'left-source')
    expect(down).toBeUndefined()
  })

  it('recalculates a measured map onto the same U-turn', () => {
    const loaded = loadFlowMapSpec({
      title: 'Trip',
      orientation: 'horizontal',
      steps: ['A', 'B', 'C', 'D', 'E', 'F'],
    })
    const dims = Object.fromEntries(
      loaded.nodes.map((node) => [node.id, { width: 120, height: 48 }])
    )
    const laidOut = recalculateFlowMapLayout(loaded.nodes, dims)
    const fifth = byText(laidOut, 'E')
    const sixth = byText(laidOut, 'F')
    expect(sixth.position?.y ?? 0).toBeGreaterThan(fifth.position?.y ?? 0)
    expect(Math.abs((sixth.position?.x ?? 0) - (fifth.position?.x ?? 0))).toBeLessThan(1)
  })
})
