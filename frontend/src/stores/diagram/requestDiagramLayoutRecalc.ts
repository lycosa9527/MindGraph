import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

/**
 * Force a layout pass from current measured sizes.
 * Mind maps use the coalesced scheduler; other types bump the generic trigger.
 */
export function requestDiagramLayoutRecalc(ctx: DiagramContext): void {
  if (isDiagramPresentationReadOnly(ctx)) {
    return
  }
  const diagramType = ctx.type.value
  if (!diagramType) {
    return
  }
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    ctx.scheduleMindMapRecalc()
    return
  }
  if (diagramType === 'multi_flow_map') {
    ctx.multiFlowMapRecalcTrigger.value += 1
  }
  ctx.layoutRecalcTrigger.value += 1
}
