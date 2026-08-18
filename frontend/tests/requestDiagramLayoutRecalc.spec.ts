import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { setPresentationDiagramEditLocked } from '@/composables/presentation/presentationDiagramEdit'
import { requestDiagramLayoutRecalc } from '@/stores/diagram/requestDiagramLayoutRecalc'
import type { DiagramContext } from '@/stores/diagram/types'

function makeCtx(overrides: Partial<DiagramContext> = {}): DiagramContext {
  return {
    type: ref('bubble_map'),
    isReadonly: ref(false),
    layoutRecalcTrigger: ref(0),
    multiFlowMapRecalcTrigger: ref(0),
    scheduleMindMapRecalc: vi.fn(),
    ...overrides,
  } as DiagramContext
}

describe('requestDiagramLayoutRecalc', () => {
  beforeEach(() => {
    setPresentationDiagramEditLocked(false)
  })

  it('schedules a mind-map recalc without bumping thinking-map triggers', () => {
    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeCtx({
      type: ref('mindmap'),
      scheduleMindMapRecalc,
    })

    requestDiagramLayoutRecalc(ctx)

    expect(scheduleMindMapRecalc).toHaveBeenCalledTimes(1)
    expect(ctx.layoutRecalcTrigger.value).toBe(0)
    expect(ctx.multiFlowMapRecalcTrigger.value).toBe(0)
  })

  it('bumps the generic layout trigger for thinking maps', () => {
    const ctx = makeCtx({ type: ref('circle_map') })

    requestDiagramLayoutRecalc(ctx)

    expect(ctx.scheduleMindMapRecalc).not.toHaveBeenCalled()
    expect(ctx.layoutRecalcTrigger.value).toBe(1)
    expect(ctx.multiFlowMapRecalcTrigger.value).toBe(0)
  })

  it('bumps both multi-flow triggers', () => {
    const ctx = makeCtx({ type: ref('multi_flow_map') })

    requestDiagramLayoutRecalc(ctx)

    expect(ctx.layoutRecalcTrigger.value).toBe(1)
    expect(ctx.multiFlowMapRecalcTrigger.value).toBe(1)
  })

  it('no-ops when the session is readonly', () => {
    const scheduleMindMapRecalc = vi.fn()
    const ctx = makeCtx({
      type: ref('mind_map'),
      isReadonly: ref(true),
      scheduleMindMapRecalc,
    })

    requestDiagramLayoutRecalc(ctx)

    expect(scheduleMindMapRecalc).not.toHaveBeenCalled()
    expect(ctx.layoutRecalcTrigger.value).toBe(0)
  })

  it('no-ops when no diagram type is set', () => {
    const ctx = makeCtx({ type: ref(null) })

    requestDiagramLayoutRecalc(ctx)

    expect(ctx.scheduleMindMapRecalc).not.toHaveBeenCalled()
    expect(ctx.layoutRecalcTrigger.value).toBe(0)
  })
})
