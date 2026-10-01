/**
 * Scale for a one-line bilingual row.
 * `usedAtScale` is the laid-out width at `currentScale` (1 = the card's font size).
 * Returns 1 when the row already fits.
 */
export function besideFitScale(
  available: number,
  usedAtScale: number,
  currentScale: number
): number {
  if (!(available > 0) || !(currentScale > 0) || !(usedAtScale > 0)) return 1
  const natural = usedAtScale / currentScale
  if (natural <= available + 0.5) return 1
  return Math.max(0.42, available / natural)
}
