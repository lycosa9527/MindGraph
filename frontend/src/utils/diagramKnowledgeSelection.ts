/**
 * Per-diagram personal-knowledge choice.
 * An empty folder never becomes the selection, and clicking the current folder clears it.
 */

export function nextKnowledgeFolderId(
  current: number | null,
  folderId: number,
  ready: boolean
): number | null {
  if (current === folderId) return null
  if (!ready) return current
  return folderId
}

export function knowledgeButtonOn(packageId: number | null, ready: boolean): boolean {
  return packageId !== null && ready
}
