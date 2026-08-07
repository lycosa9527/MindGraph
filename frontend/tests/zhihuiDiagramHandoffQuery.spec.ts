import { describe, expect, it } from 'vitest'

import {
  parseZhihuiDiagramHandoffQuery,
  ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS,
} from '@/composables/zhihui/zhihuiDiagramHandoffQuery'

describe('parseZhihuiDiagramHandoffQuery', () => {
  it('reads mode, diagramId, and title from canvas handoff query', () => {
    expect(
      parseZhihuiDiagramHandoffQuery({
        mode: 'diagram',
        diagramId: 'abc-123',
        diagramTitle: '光合作用',
      })
    ).toEqual({
      mode: 'diagram',
      diagramId: 'abc-123',
      diagramTitle: '光合作用',
      conversationId: null,
    })
  })

  it('treats diagramId alone as diagram mode', () => {
    expect(parseZhihuiDiagramHandoffQuery({ diagram_id: 'x' })).toEqual({
      mode: 'diagram',
      diagramId: 'x',
      diagramTitle: null,
      conversationId: null,
    })
  })

  it('reads conversationId and implies diagram mode', () => {
    expect(
      parseZhihuiDiagramHandoffQuery({
        conversationId: 'conv-9',
        diagramTitle: '已有会话',
      })
    ).toEqual({
      mode: 'diagram',
      diagramId: null,
      diagramTitle: '已有会话',
      conversationId: 'conv-9',
    })
  })

  it('accepts snake_case conversation_id', () => {
    expect(
      parseZhihuiDiagramHandoffQuery({ conversation_id: 'conv-snake' })
    ).toEqual({
      mode: 'diagram',
      diagramId: null,
      diagramTitle: null,
      conversationId: 'conv-snake',
    })
  })

  it('returns empty handoff for unrelated query', () => {
    expect(parseZhihuiDiagramHandoffQuery({ foo: '1' })).toEqual({
      mode: null,
      diagramId: null,
      diagramTitle: null,
      conversationId: null,
    })
  })

  it('lists keys to strip after apply', () => {
    expect(ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS).toContain('diagramId')
    expect(ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS).toContain('mode')
    expect(ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS).toContain('conversationId')
    expect(ZHIHUI_DIAGRAM_HANDOFF_QUERY_KEYS).toContain('conversation_id')
  })
})
