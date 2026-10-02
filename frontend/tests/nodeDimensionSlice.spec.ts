import { ref } from 'vue'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { useNodeDimensionSlice } from '@/stores/diagram/nodeDimensionSlice'
import type { DiagramContext } from '@/stores/diagram/types'

function makeCtx(): DiagramContext {
  return {
    nodeDimensions: ref({}),
    layoutRecalcTrigger: ref(0),
    layoutMeasureSettling: ref(false),
  } as DiagramContext
}

describe('useNodeDimensionSlice measure batch', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('does not relayout until every node has reported once', () => {
    const ctx = makeCtx()
    const slice = useNodeDimensionSlice(ctx)
    slice.setExpectedNodeCount(2)

    slice.setNodeDimensions('a', 40, 20)
    slice.setNodeDimensions('a', 40, 20)
    slice.setNodeDimensions('a', 48, 28)

    expect(ctx.layoutRecalcTrigger.value).toBe(0)
    expect(ctx.layoutMeasureSettling.value).toBe(true)
    expect(ctx.nodeDimensions.value.a).toEqual({ width: 48, height: 28 })

    slice.setNodeDimensions('b', 30, 16)

    expect(ctx.layoutRecalcTrigger.value).toBe(1)
    expect(ctx.nodeDimensions.value.b).toEqual({ width: 30, height: 16 })
  })

  it('flushes once when reports stop before the full set arrives', () => {
    vi.useFakeTimers()
    const ctx = makeCtx()
    const slice = useNodeDimensionSlice(ctx)
    slice.setExpectedNodeCount(3)

    slice.setNodeDimensions('a', 10, 10)
    expect(ctx.layoutRecalcTrigger.value).toBe(0)

    vi.advanceTimersByTime(64)

    expect(ctx.layoutRecalcTrigger.value).toBe(1)
  })

  it('live mode still relayouts on a real size change', () => {
    const ctx = makeCtx()
    const slice = useNodeDimensionSlice(ctx)

    slice.setNodeDimensions('a', 10, 10)
    slice.setNodeDimensions('a', 10, 10)
    slice.setNodeDimensions('a', 22, 10)

    expect(ctx.layoutRecalcTrigger.value).toBe(2)
  })
})
