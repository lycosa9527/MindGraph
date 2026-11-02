/**
 * Shared course-builder ribbon. Canvas tabs join the centered course tabs,
 * and canvas tools move into the same card. Course tools stay on this route.
 */
import { ref } from 'vue'

export const BUILDER_CANVAS_TABS_TARGET = 'builder-canvas-ribbon-tabs'
export const BUILDER_CANVAS_TOOLS_TARGET = 'builder-canvas-ribbon-tools'

export const builderCanvasRibbonHosted = ref(false)
export const builderRibbonToolOwner = ref<'course' | 'canvas'>('course')

let ribbonClaims = 0

export function claimBuilderCanvasRibbon(): () => void {
  ribbonClaims += 1
  builderCanvasRibbonHosted.value = true
  let released = false
  return () => {
    if (released) return
    released = true
    ribbonClaims = Math.max(0, ribbonClaims - 1)
    builderCanvasRibbonHosted.value = ribbonClaims > 0
    if (ribbonClaims === 0) builderRibbonToolOwner.value = 'course'
  }
}
