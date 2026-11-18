import { describe, expect, it } from 'vitest'

import { loadFlowMapSpec, recalculateFlowMapLayout } from '@/stores/specLoader/flowMap'
import {
  DEFAULT_FLOW_SUBSTEP_ARRANGEMENT,
  normalizeFlowSubstepArrangement,
  resolveFlowMapSubstepArrangement,
} from '@/utils/flowMapSubstepArrangement'

describe('flowMapSubstepArrangement', () => {
  it('defaults to row and only accepts stack as the alternate', () => {
    expect(DEFAULT_FLOW_SUBSTEP_ARRANGEMENT).toBe('row')
    expect(normalizeFlowSubstepArrangement(undefined)).toBe('row')
    expect(normalizeFlowSubstepArrangement('row')).toBe('row')
    expect(normalizeFlowSubstepArrangement('stack')).toBe('stack')
    expect(normalizeFlowSubstepArrangement('other')).toBe('row')
  })

  it('prefers topic data over diagram root', () => {
    expect(
      resolveFlowMapSubstepArrangement(
        { data: { substepArrangement: 'stack' } },
        { substepArrangement: 'row' }
      )
    ).toBe('stack')
    expect(resolveFlowMapSubstepArrangement(undefined, { substepArrangement: 'stack' })).toBe(
      'stack'
    )
    expect(resolveFlowMapSubstepArrangement(undefined, undefined)).toBe('row')
  })

  it('places horizontal substeps side by side in row mode', () => {
    const loaded = loadFlowMapSpec({
      title: 'Brew',
      orientation: 'horizontal',
      substepArrangement: 'row',
      steps: ['Boil', 'Steep'],
      substeps: [
        { step: 'Boil', substeps: ['Fill', 'Heat', 'Pour'] },
        { step: 'Steep', substeps: ['Wait'] },
      ],
    })
    const nodes = recalculateFlowMapLayout(loaded.nodes)
    const boilSubs = nodes
      .filter((n) => n.type === 'flowSubstep' && ['Fill', 'Heat', 'Pour'].includes(n.text ?? ''))
      .sort((a, b) => (a.position?.x ?? 0) - (b.position?.x ?? 0))
    expect(boilSubs).toHaveLength(3)
    const [fill, heat, pour] = boilSubs
    const y0 = fill?.position?.y ?? 0
    expect(boilSubs.every((n) => Math.abs((n.position?.y ?? 0) - y0) < 1)).toBe(true)
    expect(heat?.position?.x ?? 0).toBeGreaterThan(fill?.position?.x ?? 0)
    expect(pour?.position?.x ?? 0).toBeGreaterThan(heat?.position?.x ?? 0)
  })

  it('stacks horizontal substeps vertically in stack mode', () => {
    const loaded = loadFlowMapSpec({
      title: 'Brew',
      orientation: 'horizontal',
      substepArrangement: 'stack',
      steps: ['Boil'],
      substeps: [{ step: 'Boil', substeps: ['Fill', 'Heat', 'Pour'] }],
    })
    const nodes = recalculateFlowMapLayout(loaded.nodes)
    const boilSubs = nodes
      .filter((n) => n.type === 'flowSubstep')
      .sort((a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0))
    expect(boilSubs).toHaveLength(3)
    const [fill, heat, pour] = boilSubs
    const x0 = fill?.position?.x ?? 0
    // Stack centers each pill; x can differ slightly by width, but y must increase.
    expect(heat?.position?.y ?? 0).toBeGreaterThan(fill?.position?.y ?? 0)
    expect(pour?.position?.y ?? 0).toBeGreaterThan(heat?.position?.y ?? 0)
    expect(Math.abs((heat?.position?.x ?? 0) - x0)).toBeLessThan(40)
  })

  it('stamps substepArrangement onto the topic node and metadata', () => {
    const loaded = loadFlowMapSpec({
      title: 'T',
      steps: ['A'],
      substeps: [],
      substepArrangement: 'stack',
    })
    const topic = loaded.nodes.find((n) => n.id === 'flow-topic')
    expect(topic?.data?.substepArrangement).toBe('stack')
    expect(loaded.metadata?.substepArrangement).toBe('stack')
  })
})
