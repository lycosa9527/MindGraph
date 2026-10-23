import { describe, expect, it } from 'vitest'

import { AI_BRAINSTORM_NEXT, AI_BRAINSTORM_START } from '@/composables/aiBrainstorm/constants'
import { buildDiagramData } from '@/composables/aiBrainstorm/diagramDataBuilder'

describe('AI brainstorm payload for every diagram', () => {
  it('posts to the renamed brainstorm routes', () => {
    expect(AI_BRAINSTORM_START).toBe('/thinking_mode/ai_brainstorm/start')
    expect(AI_BRAINSTORM_NEXT).toBe('/thinking_mode/ai_brainstorm/next_batch')
  })

  it('builds the center field each diagram type sends to start', () => {
    expect(
      buildDiagramData('circle_map', [{ id: 'topic', text: '水循环', type: 'topic' }])
    ).toMatchObject({
      topic: '水循环',
      center: { text: '水循环' },
    })
    expect(
      buildDiagramData('bubble_map', [{ id: 'topic', text: '太阳', type: 'topic' }])
    ).toMatchObject({
      topic: '太阳',
      center: { text: '太阳' },
    })
    expect(
      buildDiagramData('double_bubble_map', [
        { id: 'left-topic', text: '电场', type: 'topic' },
        { id: 'right-topic', text: '磁场', type: 'topic' },
      ])
    ).toEqual({ left: '电场', right: '磁场' })
    expect(
      buildDiagramData('multi_flow_map', [{ id: 'event', text: '下雨', type: 'event' }])
    ).toEqual({ event: '下雨' })
    expect(
      buildDiagramData('flow_map', [{ id: 'flow-topic', text: '泡茶', type: 'topic' }])
    ).toEqual({
      title: '泡茶',
    })
    expect(
      buildDiagramData('brace_map', [{ id: 'topic', text: '自行车', type: 'topic' }])
    ).toMatchObject({
      whole: '自行车',
    })
    expect(
      buildDiagramData('tree_map', [{ id: 'topic', text: '动物', type: 'topic' }])
    ).toMatchObject({
      topic: '动物',
    })
    expect(
      buildDiagramData('bridge_map', [{ id: 'dimension', text: '功能', type: 'dimension' }])
    ).toMatchObject({
      dimension: '功能',
    })
    expect(
      buildDiagramData('mindmap', [{ id: 'topic', text: '光合作用', type: 'topic' }])
    ).toMatchObject({
      topic: '光合作用',
    })
    expect(
      buildDiagramData('mind_map', [{ id: 'topic', text: '光合作用', type: 'topic' }])
    ).toMatchObject({
      topic: '光合作用',
    })
    expect(
      buildDiagramData('concept_map', [{ id: 'topic', text: '生态系统', type: 'topic' }])
    ).toMatchObject({
      topic: '生态系统',
    })
  })
})
