/**
 * Shared text normalization for CmapTools import and graphical layout keys.
 */
export function normalizeLabel(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}
