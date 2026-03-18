import type { Position } from '@/types'

import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useCustomPositionsSlice(ctx: DiagramContext) {
  const { data, type } = ctx

  function saveCustomPosition(nodeId: string, x: number, y: number): void {
    if (!data.value) return

    if (!data.value._customPositions) {
      data.value._customPositions = {}
    }

    data.value._customPositions[nodeId] = { x, y }
    emitEvent('diagram:position_changed', { nodeId, position: { x, y }, isCustom: true })
  }

  function hasCustomPosition(nodeId: string): boolean {
    return !!data.value?._customPositions?.[nodeId]
  }

  function getCustomPosition(nodeId: string): Position | undefined {
    return data.value?._customPositions?.[nodeId]
  }

  function clearCustomPosition(nodeId: string): void {
    if (data.value?._customPositions?.[nodeId]) {
      delete data.value._customPositions[nodeId]
    }
  }

  function resetToAutoLayout(): void {
    if (data.value) {
      data.value._customPositions = {}
      emitEvent('diagram:layout_reset', { type: type.value })
    }
  }

  return {
    saveCustomPosition,
    hasCustomPosition,
    getCustomPosition,
    clearCustomPosition,
    resetToAutoLayout,
  }
}
