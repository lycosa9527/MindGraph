/**
 * Classroom e-blackboard chrome: larger mind-map +/- and collapse controls.
 * Keep the scale here so we can tweak without hunting CSS.
 */
export const MIND_MAP_E_BLACKBOARD_CONTROL_SCALE = 2

export function mindMapControlScale(eBlackboardOptimize: boolean): number {
  return eBlackboardOptimize ? MIND_MAP_E_BLACKBOARD_CONTROL_SCALE : 1
}
