/**
 * Stream chevron visibility (Zulip-style).
 *
 * Zulip keeps the expand control from stream metadata (`topic_count` on
 * GET /channels). It does not fetch every stream's topic list on sidebar
 * mount just to decide whether a chevron should show.
 */
export function channelTopicChevronVisible(topicCount: number, loadedTopicCount: number): boolean {
  return topicCount > 0 || loadedTopicCount > 0
}
