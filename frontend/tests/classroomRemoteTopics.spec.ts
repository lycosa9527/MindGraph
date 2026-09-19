import { describe, expect, it } from 'vitest'

import {
  DEFAULT_CLASSROOM_REMOTE_TOPICS,
  applyClassroomRemoteTopic,
  formatClassroomRemoteVsTopic,
  normalizeClassroomRemoteTopic,
  parseClassroomRemoteTopics,
  readDiagramCenterTopic,
  splitClassroomRemoteVsTopic,
} from '@/canvas-ribbon/classroomRemoteTopics'

describe('classroom remote topics', () => {
  it('normalizes and parses a stored topic list', () => {
    expect(normalizeClassroomRemoteTopic('  光合  作用  ')).toBe('光合 作用')
    expect(parseClassroomRemoteTopics(null)).toBeNull()
    expect(parseClassroomRemoteTopics('{"no":"array"}')).toBeNull()
    expect(parseClassroomRemoteTopics(JSON.stringify(['光合作用', '', '  水循环  ']))).toEqual([
      '光合作用',
      '水循环',
    ])
    expect(DEFAULT_CLASSROOM_REMOTE_TOPICS).toContain('光合作用')
    expect(DEFAULT_CLASSROOM_REMOTE_TOPICS).toContain('植物细胞 vs 动物细胞')
  })

  it('splits dual bubble topics on vs', () => {
    expect(splitClassroomRemoteVsTopic('植物细胞 vs 动物细胞')).toEqual({
      left: '植物细胞',
      right: '动物细胞',
    })
    expect(splitClassroomRemoteVsTopic('Cats VS. Dogs')).toEqual({
      left: 'Cats',
      right: 'Dogs',
    })
    expect(splitClassroomRemoteVsTopic('光合作用')).toBeNull()
    expect(formatClassroomRemoteVsTopic('植物细胞', '动物细胞')).toBe('植物细胞 vs 动物细胞')
  })

  it('overrides the center topic on the current diagram', () => {
    const nodes = [{ id: 'topic', type: 'topic', text: '中心主题' }]
    const store = {
      type: 'mindmap',
      data: { nodes },
      updateNode: (nodeId: string, updates: { text?: string }) => {
        const node = nodes.find((item) => item.id === nodeId)
        if (!node || typeof updates.text !== 'string') {
          return false
        }
        node.text = updates.text
        return true
      },
    }
    expect(applyClassroomRemoteTopic(store as never, '光合作用')).toBe(true)
    expect(readDiagramCenterTopic(store as never)).toBe('光合作用')
    expect(applyClassroomRemoteTopic(store as never, '   ')).toBe(false)
  })

  it('applies vs pairs to both double-bubble centers', () => {
    const nodes = [
      { id: 'left-topic', type: 'topic', text: '主题A' },
      { id: 'right-topic', type: 'topic', text: '主题B' },
    ]
    const store = {
      type: 'double_bubble_map',
      data: { nodes },
      updateNode: (nodeId: string, updates: { text?: string }) => {
        const node = nodes.find((item) => item.id === nodeId)
        if (!node || typeof updates.text !== 'string') {
          return false
        }
        node.text = updates.text
        return true
      },
    }
    expect(applyClassroomRemoteTopic(store as never, '植物细胞 vs 动物细胞')).toBe(true)
    expect(nodes[0].text).toBe('植物细胞')
    expect(nodes[1].text).toBe('动物细胞')
    expect(readDiagramCenterTopic(store as never)).toBe('植物细胞 vs 动物细胞')
  })
})
