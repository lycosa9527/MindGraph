import { getDefaultDiagramName } from '@/composables/editor/useDiagramLabels'

/**
 * Title persisted to the library. Uses effectiveTitle (user rename > topic > default)
 * rather than raw topic node text alone.
 */
export function resolveDiagramTitleForSave(
  effectiveTitle: string | null | undefined,
  diagramType: string | null,
  language: string
): string {
  const trimmed = effectiveTitle?.trim()
  if (trimmed) return trimmed
  return getDefaultDiagramName(diagramType, language)
}
