import { describe, expect, it } from 'vitest'

import {
  findChannelInTree,
  flattenChannels,
  joinedUnreadTotal,
  mergeTopicsByChannel,
  topicsForChannel,
} from '@/utils/workshopChannelTree'

const tree = [
  {
    id: 1,
    is_joined: true,
    unread_count: 0,
    children: [
      { id: 11, is_joined: true, unread_count: 4 },
      { id: 12, is_joined: false, unread_count: 9 },
    ],
  },
  {
    id: 2,
    is_joined: true,
    unread_count: 1,
  },
]

describe('flattenChannels', () => {
  it('includes group rows and nested lesson children', () => {
    expect(flattenChannels(tree).map((row) => row.id)).toEqual([1, 11, 12, 2])
  })
})

describe('findChannelInTree', () => {
  it('finds a nested lesson by id', () => {
    expect(findChannelInTree(tree, 11)?.id).toBe(11)
    expect(findChannelInTree(tree, 99)).toBeNull()
  })
})

describe('joinedUnreadTotal', () => {
  it('sums unread on joined children and announce, not unjoined lessons', () => {
    expect(joinedUnreadTotal(tree)).toBe(5)
  })
})

describe('mergeTopicsByChannel', () => {
  it('replaces one stream without dropping topics from other lessons', () => {
    const existing = [
      { id: 1, channel_id: 11, title: 'old-a' },
      { id: 2, channel_id: 12, title: 'keep' },
    ]
    const next = mergeTopicsByChannel(existing, 11, [{ id: 3, channel_id: 11, title: 'new-a' }])
    expect(next.map((row) => row.id)).toEqual([2, 3])
  })
})

describe('topicsForChannel', () => {
  it('returns only topics for the open lesson', () => {
    const topics = [
      { id: 1, channel_id: 11, title: '课前讨论' },
      { id: 2, channel_id: 12, title: '课后反思' },
    ]
    expect(topicsForChannel(topics, 11).map((row) => row.title)).toEqual(['课前讨论'])
    expect(topicsForChannel(topics, null)).toEqual([])
  })
})
