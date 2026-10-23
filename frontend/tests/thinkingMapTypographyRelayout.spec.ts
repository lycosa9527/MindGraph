import { ref } from 'vue'

import { describe, expect, it, vi } from 'vitest'

import {
  applyThinkingMapTypographyRelayout,
  nodeStylePatchHasTypography,
} from '@/stores/diagram/thinkingMapTypographyRelayout'
import type { DiagramContext } from '@/stores/diagram/types'
import type { DiagramNode } from '@/types'

function mockCtx(diagramType: string): DiagramContext {
  return {
    type: ref(diagramType),
    nodeDimensions: ref({}),
    layoutRecalcTrigger: ref(0),
    multiFlowMapRecalcTrigger: ref(0),
    viewBus: { emit: vi.fn() },
  } as unknown as DiagramContext
}

describe('thinkingMapTypographyRelayout', () => {
  it('detects typography style patches', () => {
    expect(nodeStylePatchHasTypography(undefined)).toBe(false)
    expect(nodeStylePatchHasTypography({ textColor: '#000' })).toBe(false)
    expect(nodeStylePatchHasTypography({ fontStyle: 'italic' })).toBe(true)
    expect(nodeStylePatchHasTypography({ textDecoration: 'underline' })).toBe(true)
  })

  it('relayouts multi-flow nodes on italic and underline toggles', () => {
    const ctx = mockCtx('multi_flow_map')
    const cause: DiagramNode = { id: 'cause-1', text: 'Cause', type: 'flow' }
    applyThinkingMapTypographyRelayout(ctx, 'cause-1', cause, { fontStyle: 'italic' })
    expect(ctx.nodeDimensions.value['cause-1']).toBeUndefined()
    expect(ctx.multiFlowMapRecalcTrigger.value).toBe(1)
    expect(ctx.layoutRecalcTrigger.value).toBe(1)
  })

  it('relayouts tree and bridge dimension labels', () => {
    const treeCtx = mockCtx('tree_map')
    const dim: DiagramNode = { id: 'dimension-label', text: '分类', type: 'label' }
    applyThinkingMapTypographyRelayout(treeCtx, 'dimension-label', dim, { fontSize: 18 })
    expect(treeCtx.layoutRecalcTrigger.value).toBe(1)

    const bridgeCtx = mockCtx('bridge_map')
    const bridgeDim: DiagramNode = { id: 'dimension-label', text: '类比', type: 'label' }
    applyThinkingMapTypographyRelayout(bridgeCtx, 'dimension-label', bridgeDim, {
      fontStyle: 'italic',
    })
    expect(bridgeCtx.layoutRecalcTrigger.value).toBe(1)
  })

  it('requests double-bubble rebuild without the generic trigger', () => {
    const ctx = mockCtx('double_bubble_map')
    const node: DiagramNode = { id: 'left-0', text: 'A', type: 'bubble' }
    applyThinkingMapTypographyRelayout(ctx, 'left-0', node, { textDecoration: 'underline' })
    expect(ctx.viewBus.emit).toHaveBeenCalledWith('diagram:double_bubble_relayout_requested', {})
    expect(ctx.layoutRecalcTrigger.value).toBe(0)
  })
})
