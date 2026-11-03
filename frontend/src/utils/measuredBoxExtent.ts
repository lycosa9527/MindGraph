/**
 * Pick the box extent layout should use.
 * A reading at the CSS minimum is the real box for a short label. It is the
 * pre-font collapse only when the estimate is well above that minimum.
 */
export const MEASURED_BOX_COLLAPSE_SLACK_PX = 16

export function measuredBoxExtent(
  measured: number | undefined,
  estimated: number,
  floor: number
): number {
  if (measured == null || !Number.isFinite(measured) || measured < 1) return estimated
  if (measured <= floor && estimated > measured + MEASURED_BOX_COLLAPSE_SLACK_PX) {
    return estimated
  }
  return measured
}
