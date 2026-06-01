/** Zero means no per-user saved-diagram cap (paid / personal accounts). */
export const DIAGRAM_SAVE_LIMIT_UNLIMITED = 0

export function hasDiagramSaveLimit(maxDiagrams: number): boolean {
  return maxDiagrams > 0
}

export function formatDiagramCountLabel(count: number, maxDiagrams: number): string {
  if (!hasDiagramSaveLimit(maxDiagrams)) {
    return String(count)
  }
  return `${count}/${maxDiagrams}`
}
