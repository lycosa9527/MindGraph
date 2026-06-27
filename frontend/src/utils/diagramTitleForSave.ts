import { getDefaultDiagramName } from '@/composables/editor/useDiagramLabels'
import type { LocaleCode } from '@/i18n/locales'

/**
 * Title persisted to the library. Uses effectiveTitle (user rename > topic > default)
 * rather than raw topic node text alone.
 */
export function resolveDiagramTitleForSave(
  effectiveTitle: string | null | undefined,
  diagramType: string | null,
  language: LocaleCode
): string {
  const trimmed = effectiveTitle?.trim()
  if (trimmed) return trimmed
  return getDefaultDiagramName(diagramType, language)
}
