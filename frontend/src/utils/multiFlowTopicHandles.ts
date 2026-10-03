export interface MultiFlowTopicHandle {
  id: string
  top: string
  transform: string
}

const HANDLE_TRANSFORM = 'translateY(-50%)'

/** Even slots down one side, with a margin at the top and the bottom. */
export function multiFlowTopicHandleTopPercent(index: number, count: number): number {
  if (count <= 1) return 50
  return ((index + 1) / (count + 1)) * 100
}

/**
 * One handle per cause (left) or effect (right), spaced evenly on that side.
 * The event pill keeps its own height.
 */
export function buildMultiFlowTopicHandles(
  side: 'left' | 'right',
  count: number
): MultiFlowTopicHandle[] {
  if (count <= 0) return []
  const prefix = side === 'left' ? 'left' : 'right'
  return Array.from({ length: count }, (_, index) => ({
    id: `${prefix}-${index}`,
    top: `${multiFlowTopicHandleTopPercent(index, count)}%`,
    transform: HANDLE_TRANSFORM,
  }))
}
