import { describe, expect, it } from 'vitest'

import { clearDefaultTemplateCache, getDefaultTemplate } from '@/stores/specLoader/defaultTemplates'
import { loadFlowMapSpec } from '@/stores/specLoader/flowMap'

describe('flow map default template', () => {
  it('uses 3+2+0+0 substeps under four steps', () => {
    clearDefaultTemplateCache()
    const spec = getDefaultTemplate('flow_map', 'en')
    expect(spec).toBeTruthy()
    if (!spec) return
    expect(spec.substepArrangement).toBe('row')
    expect(spec.orientation).toBe('horizontal')
    expect(spec.steps).toHaveLength(4)
    const groups = spec.substeps as Array<{ substeps: string[]; stepIndex?: number }>
    expect(groups.map((g) => g.substeps.length)).toEqual([3, 2, 0, 0])
    expect(groups.map((g) => g.stepIndex)).toEqual([0, 1, 2, 3])

    const loaded = loadFlowMapSpec(spec)
    const steps = loaded.nodes.filter((n) => n.type === 'flow')
    const subs = loaded.nodes.filter((n) => n.type === 'flowSubstep')
    expect(steps).toHaveLength(4)
    expect(subs).toHaveLength(5)

    const counts = steps.map(
      (step, index) =>
        subs.filter(
          (n) =>
            n.data?.parentStepId === step.id ||
            n.data?.stepIndex === index ||
            n.data?.stepIndex === step.data?.stepIndex
        ).length
    )
    expect(counts).toEqual([3, 2, 0, 0])
  })
})
