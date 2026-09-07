/**
 * Walk the teaching-group tree. Lesson-study rows live on ``children``.
 */
export interface ChannelTreeNode {
  id: number
  is_joined: boolean
  unread_count: number
  children?: this[]
}

export function flattenChannels<T extends ChannelTreeNode>(channels: T[]): T[] {
  const out: T[] = []
  for (const group of channels) {
    out.push(group)
    const children = group.children
    if (children?.length) {
      out.push(...children)
    }
  }
  return out
}

export function findChannelInTree<T extends ChannelTreeNode>(
  channels: T[],
  channelId: number
): T | null {
  for (const group of channels) {
    if (group.id === channelId) {
      return group
    }
    for (const child of group.children ?? []) {
      if (child.id === channelId) {
        return child
      }
    }
  }
  return null
}

export function mergeTopicsByChannel<T extends { channel_id: number }>(
  existing: T[],
  channelId: number,
  incoming: T[]
): T[] {
  return [...existing.filter((topic) => topic.channel_id !== channelId), ...incoming]
}

export function topicsForChannel<T extends { channel_id: number }>(
  topics: T[],
  channelId: number | null
): T[] {
  if (channelId == null) {
    return []
  }
  return topics.filter((topic) => topic.channel_id === channelId)
}

export function joinedUnreadTotal<T extends ChannelTreeNode>(channels: T[]): number {
  return flattenChannels(channels).reduce((sum, channel) => {
    if (!channel.is_joined) {
      return sum
    }
    return sum + (channel.unread_count || 0)
  }, 0)
}
