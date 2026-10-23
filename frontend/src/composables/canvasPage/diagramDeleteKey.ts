/**
 * Canvas Delete / Backspace.
 * Vue Flow's default key is Backspace only, and it removes the node from the
 * canvas list without updating the diagram. The next selection refresh paints
 * the node again. The editor owns deletion and asks Vue Flow not to.
 */

export function isDiagramDeleteKey(event: { key: string; code: string }): boolean {
  return (
    event.key === 'Delete' ||
    event.key === 'Backspace' ||
    event.code === 'Delete' ||
    event.code === 'Backspace'
  )
}

/**
 * The highlighted canvas nodes win. The diagram store is the fallback when
 * Vue Flow has not marked a selection yet.
 */
export function resolveDiagramDeleteNodeIds(
  canvasSelectedIds: readonly string[],
  storeSelectedIds: readonly string[]
): string[] {
  const canvasIds = canvasSelectedIds.filter((id) => id.length > 0)
  if (canvasIds.length > 0) return [...canvasIds]
  return storeSelectedIds.filter((id) => id.length > 0)
}
