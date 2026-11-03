/** Which line a node double-click should open. */
export type NodeTextEditLine = 'primary' | 'secondary'

/**
 * A plain double-click edits the main line.
 * Ctrl or Command with the double-click edits the smaller second line.
 */
export function nodeTextEditLine(
  event: { ctrlKey?: boolean; metaKey?: boolean },
  bilingual: boolean
): NodeTextEditLine {
  if (!bilingual) return 'primary'
  if (event.ctrlKey || event.metaKey) return 'secondary'
  return 'primary'
}
