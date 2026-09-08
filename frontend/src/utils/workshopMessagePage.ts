/**
 * Infer Zulip `found_oldest` when the API does not return that flag.
 * A before-only page that is shorter than the requested window has reached
 * the start of the thread.
 */
export function inferFoundOldest(
  incomingCount: number,
  numBefore: number,
  numAfter: number
): boolean {
  if (numAfter > 0) {
    return false
  }
  return incomingCount < numBefore
}
