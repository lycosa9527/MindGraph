import { type Ref, ref } from 'vue'

/**
 * Click on empty canvas clears the selection so the follow-node toolbar closes.
 * A drag (pointer moved more than a few pixels) keeps the selection.
 */
export function useDiagramFollowNodeDismiss(options: {
  enabled: () => boolean
  suppressUntil: Ref<number>
  selectedCount: () => number
  clearSelection: () => void
}): {
  onPointerDown: (event: PointerEvent) => void
  onPointerUp: (event: PointerEvent) => void
} {
  const pointerDown = ref<{ x: number; y: number } | null>(null)

  function onPointerDown(event: PointerEvent): void {
    if (!options.enabled()) return
    pointerDown.value = { x: event.clientX, y: event.clientY }
  }

  function onPointerUp(event: PointerEvent): void {
    const start = pointerDown.value
    pointerDown.value = null
    if (!options.enabled() || !start) return
    if (Date.now() < options.suppressUntil.value) return
    if (Math.abs(event.clientX - start.x) > 4 || Math.abs(event.clientY - start.y) > 4) return
    const target = event.target
    if (!(target instanceof Element)) return
    if (
      target.closest(
        '.vue-flow__node, .node-floating-toolbar, .node-floating-toolbar-popper, .context-menu, .ne-bubble, .vue-flow__minimap, .el-popper'
      )
    ) {
      return
    }
    if (!target.closest('.vue-flow')) return
    if (options.selectedCount() === 0) return
    options.clearSelection()
  }

  return { onPointerDown, onPointerUp }
}
