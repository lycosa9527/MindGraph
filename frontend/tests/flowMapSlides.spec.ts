import { describe, expect, it } from 'vitest'

import type { DiagramNode } from '@/types'
import {
  FLOW_TOPIC_NODE_ID,
  stampFlowMapStepData,
  stampFlowMapSubstepData,
} from '@/utils/flowMapIdentity'
import { buildFlowMapSlides } from '@/utils/flowMapSlides'

function topic(text: string): DiagramNode {
  return {
    id: FLOW_TOPIC_NODE_ID,
    text,
    type: 'topic',
    position: { x: 0, y: 0 },
  }
}

function step(id: string, text: string, index: number): DiagramNode {
  return {
    id,
    text,
    type: 'flow',
    position: { x: 0, y: 0 },
    data: stampFlowMapStepData(index),
  }
}

function substep(
  id: string,
  text: string,
  stepIndex: number,
  subIndex: number,
  parentStepId: string
): DiagramNode {
  return {
    id,
    text,
    type: 'flowSubstep',
    position: { x: 0, y: 0 },
    data: stampFlowMapSubstepData(stepIndex, subIndex, parentStepId),
  }
}

describe('buildFlowMapSlides', () => {
  const nodes: DiagramNode[] = [
    topic('水循环'),
    step('step-a', '蒸发', 0),
    step('step-b', '凝结', 1),
    step('step-c', '降水', 2),
    substep('ss-a1', '加热', 0, 0, 'step-a'),
    substep('ss-a2', '汽化', 0, 1, 'step-a'),
    substep('ss-b1', '冷却', 1, 0, 'step-b'),
  ]

  it('firstLevel walks overview → each step with its substeps focused', () => {
    const slides = buildFlowMapSlides(nodes, 'firstLevel')
    expect(slides.map((slide) => slide.id)).toEqual(['overview', 'step-a', 'step-b', 'step-c'])
    expect(slides[0]?.title).toBe('水循环')
    expect(slides[0]?.focusNodeIds).toHaveLength(nodes.length)
    expect(slides.find((slide) => slide.id === 'step-a')?.focusNodeIds).toEqual([
      'step-a',
      'ss-a1',
      'ss-a2',
    ])
    expect(slides.find((slide) => slide.id === 'step-b')?.focusNodeIds).toEqual(['step-b', 'ss-b1'])
    expect(slides.find((slide) => slide.id === 'step-c')?.focusNodeIds).toEqual(['step-c'])
    expect(slides.find((slide) => slide.id === 'step-a')?.breadcrumb).toEqual(['水循环', '蒸发'])
  })

  it('deep walks each step then its substeps in order', () => {
    const slides = buildFlowMapSlides(nodes, 'deep')
    expect(slides.map((slide) => slide.id)).toEqual([
      'overview',
      'step-a',
      'ss-a1',
      'ss-a2',
      'step-b',
      'ss-b1',
      'step-c',
    ])
    expect(slides.find((slide) => slide.id === 'ss-a1')?.focusNodeIds).toEqual(['step-a', 'ss-a1'])
    expect(slides.find((slide) => slide.id === 'ss-a1')?.breadcrumb).toEqual([
      '水循环',
      '蒸发',
      '加热',
    ])
  })

  it('returns empty for empty node list', () => {
    expect(buildFlowMapSlides([])).toEqual([])
  })
})
