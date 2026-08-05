import { toValue } from 'vue'

import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'

import type { DiagramContext } from './types'

/**
 * True when the diagram must not accept edits.
 * - Global presentation lock (slideshow / export)
 * - Per-session readonly via ctx (slice callers pass DiagramContext)
 */
export function isDiagramPresentationReadOnly(
  ctx?: Pick<DiagramContext, 'isReadonly'> | null
): boolean {
  if (diagramPresentationReadOnlyRef.value) return true
  if (ctx && toValue(ctx.isReadonly)) return true
  return false
}
