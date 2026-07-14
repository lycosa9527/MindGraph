import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'

/** True when diagram canvas is in a read-only viewer (e.g. case-square detail preview). */
export function isDiagramPresentationReadOnly(): boolean {
  return diagramPresentationReadOnlyRef.value
}
