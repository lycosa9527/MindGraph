/**
 * Horizontal node chip row for Kitty: swipe/tap to select (inline-rec style).
 */
import { computed, ref, watch } from 'vue'

import { pulseDeviceEngage, pulseDeviceSelection } from '@/composables/core/useDeviceVibration'
import { buildKittyClickWheelNodes } from '@/composables/kitty/kittyDiagramChildren'
import { applyKittySelectionTarget } from '@/composables/kitty/kittySelectionApply'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramType } from '@/types'

export interface KittyClickWheelChild {
  id: string
  index: number
  text: string
}

export interface UseKittyClickWheelOptions {
  onSelectionChange?: () => void
  canvasHighlight?: boolean
  /** Fired when the already-active chip is tapped again (e.g. open 学习提示). */
  onActiveRetap?: (node: KittyClickWheelChild) => void
}

export function useKittyClickWheel(options: UseKittyClickWheelOptions = {}) {
  const diagramStore = useDiagramStore()
  const canvasHighlight = options.canvasHighlight !== false

  const activeIndex = ref(0)

  const children = computed<KittyClickWheelChild[]>(() => {
    const dt = (diagramStore.type ?? 'circle_map') as DiagramType
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    return buildKittyClickWheelNodes(dt, nodes, connections)
  })

  const hasNodes = computed(() => children.value.length > 0)

  const activeChild = computed(() => {
    const list = children.value
    if (list.length === 0) {
      return null
    }
    const idx = Math.min(Math.max(activeIndex.value, 0), list.length - 1)
    return list[idx] ?? null
  })

  function syncIndexFromSelection(): void {
    const list = children.value
    if (list.length === 0) {
      activeIndex.value = 0
      return
    }
    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) {
      activeIndex.value = 0
      return
    }
    const found = list.findIndex((c) => c.id === selectedId)
    if (found >= 0) {
      activeIndex.value = found
    }
  }

  function selectIndex(nextIndex: number): void {
    const list = children.value
    if (list.length === 0) {
      return
    }
    const wrapped = ((nextIndex % list.length) + list.length) % list.length
    if (wrapped === activeIndex.value) {
      return
    }
    activeIndex.value = wrapped
    const child = list[wrapped]
    if (!child) {
      return
    }
    applyKittySelectionTarget({ nodeId: child.id }, { canvasHighlight })
    pulseDeviceSelection()
    options.onSelectionChange?.()
  }

  function selectById(nodeId: string): void {
    if (!nodeId) {
      return
    }
    const found = children.value.findIndex((c) => c.id === nodeId)
    if (found < 0) {
      return
    }
    if (found === activeIndex.value) {
      applyKittySelectionTarget({ nodeId }, { canvasHighlight })
      pulseDeviceEngage()
      const child = children.value[found]
      if (child) {
        options.onActiveRetap?.(child)
      }
      options.onSelectionChange?.()
      return
    }
    selectIndex(found)
  }

  function stepBy(delta: number): void {
    selectIndex(activeIndex.value + delta)
  }

  watch(
    () => [children.value.length, diagramStore.selectedNodes.join(',')] as const,
    () => {
      syncIndexFromSelection()
    },
    { immediate: true }
  )

  return {
    children,
    hasNodes,
    activeIndex,
    activeChild,
    selectIndex,
    selectById,
    stepBy,
  }
}

export type KittyClickWheelApi = ReturnType<typeof useKittyClickWheel>
