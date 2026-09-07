import { describe, expect, it } from 'vitest'

import { channelTopicChevronVisible } from '@/utils/workshopTopicChevron'

describe('channelTopicChevronVisible', () => {
  it('uses channel topic_count so the sidebar need not prefetch every topic list', () => {
    expect(channelTopicChevronVisible(3, 0)).toBe(true)
    expect(channelTopicChevronVisible(0, 0)).toBe(false)
  })

  it('stays visible after topics have been loaded for the expanded stream', () => {
    expect(channelTopicChevronVisible(0, 2)).toBe(true)
  })
})
