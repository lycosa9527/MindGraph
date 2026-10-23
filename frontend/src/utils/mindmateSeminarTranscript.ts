/** Continue session reopens the owner's saved seminar. Joiners stay on the transcript. */
export function canContinueSavedSeminar(
  sessionId: string | null,
  owned: boolean,
  inLiveRoom: boolean
): boolean {
  return Boolean(sessionId) && owned && !inLiveRoom
}
