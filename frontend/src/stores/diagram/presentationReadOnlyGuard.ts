import { type MaybeRefOrGetter, toValue } from 'vue'

import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'

/**
 * True when the diagram must not accept edits.
 * - Global presentation lock (slideshow / export)
 * - Per-session readonly via ctx / DiagramSession
 */
export function isDiagramPresentationReadOnly(
  ctx?: { isReadonly?: MaybeRefOrGetter<boolean> } | null
): boolean {
  if (diagramPresentationReadOnlyRef.value) return true
  if (ctx?.isReadonly !== undefined && toValue(ctx.isReadonly)) return true
  return false
}
