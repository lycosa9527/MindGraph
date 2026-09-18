import { describe, expect, it } from 'vitest'

import { MULTI_FLOW_MAP_TOPIC_WIDTH } from '@/composables/diagrams/layoutConfig'
import {
  estimateMultiFlowTopicWidth,
  loadMultiFlowMapSpec,
  recalculateMultiFlowMapLayout,
} from '@/stores/specLoader/multiFlowMap'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'

describe('multi-flow topic width after autocomplete', () => {
  it('estimates a long event title wider than the 事件 slot', () => {
    expect(estimateMultiFlowTopicWidth('事件')).toBe(MULTI_FLOW_MAP_TOPIC_WIDTH)
    expect(estimateMultiFlowTopicWidth('Air Pollution in Cities')).toBeGreaterThan(
      MULTI_FLOW_MAP_TOPIC_WIDTH
    )
  })

  it('keeps cause and effect columns outside a long event pill', () => {
    const loaded = loadMultiFlowMapSpec({
      event: 'Air Pollution in Cities',
      causes: ['工业排放', '汽车尾气'],
      effects: ['健康问题', '经济损失'],
    })
    const topicWidth = estimateMultiFlowTopicWidth('Air Pollution in Cities')
    const nodes = recalculateMultiFlowMapLayout(loaded.nodes, topicWidth, {}, {})
    const event = nodes.find((node) => node.id === 'event')
    expect(event).toBeDefined()
    const topicLeft = event?.position.x ?? 0
    const topicRight = topicLeft + topicWidth
    for (const cause of nodes.filter((node) => isMultiFlowCauseNode(node))) {
      const width = typeof cause.style?.width === 'number' ? cause.style.width : 0
      expect(cause.position.x + width).toBeLessThan(topicLeft)
    }
    for (const effect of nodes.filter((node) => isMultiFlowEffectNode(node))) {
      expect(effect.position.x).toBeGreaterThan(topicRight)
    }
  })

  it('pushes the effect column right when the event title is longer than 90px', () => {
    const loaded = loadMultiFlowMapSpec({
      event: 'Air Pollution in Cities',
      causes: ['A'],
      effects: ['B'],
    })
    const stale = recalculateMultiFlowMapLayout(loaded.nodes, MULTI_FLOW_MAP_TOPIC_WIDTH, {}, {})
    const measured = estimateMultiFlowTopicWidth('Air Pollution in Cities')
    const fixed = recalculateMultiFlowMapLayout(loaded.nodes, measured, {}, {})
    const staleEffect = stale.find((node) => isMultiFlowEffectNode(node))
    const fixedEffect = fixed.find((node) => isMultiFlowEffectNode(node))
    expect(fixedEffect?.position.x).toBeGreaterThan(staleEffect?.position.x ?? 0)
  })
})
