import type { CanvasInputMode } from '@/config/canvasInputMode'

/**
 * Classroom board chrome: larger mind-map +/- and collapse controls.
 * Keep the scale here so we can tweak without hunting CSS.
 */
export const MIND_MAP_E_BLACKBOARD_CONTROL_SCALE = 2

export function mindMapControlScale(mode: CanvasInputMode): number {
  return mode === 'board' ? MIND_MAP_E_BLACKBOARD_CONTROL_SCALE : 1
}
