/** Title stored on a seminar started from the MindMate home composer. */

const SEMINAR_TITLE_MAX = 40

export function seminarTitleFromTopic(topic: string): string {
  const compact = topic.replace(/\s+/g, ' ').trim()
  if (compact.length <= SEMINAR_TITLE_MAX) {
    return compact
  }
  return compact.slice(0, SEMINAR_TITLE_MAX)
}
