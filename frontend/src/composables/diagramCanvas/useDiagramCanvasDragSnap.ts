/**
 * Grid snap for user drags only.
 * With `snapToGrid` on, Vue Flow also snaps every node once when it mounts. That
 * paints the node off its layout position until the next store sync moves it
 * back. The flag is set on the state ref (not the prop) because Vue Flow moves
 * the node in the same event that emits drag start.
 */
import { useVueFlow } from '@vue-flow/core'

export function useDiagramCanvasDragSnap(vueFlowId: string): void {
  const { snapToGrid, onNodeDragStart, onNodeDragStop, onSelectionDragStart, onSelectionDragStop } =
    useVueFlow(vueFlowId)
  const begin = (): void => {
    snapToGrid.value = true
  }
  const end = (): void => {
    snapToGrid.value = false
  }
  onNodeDragStart(begin)
  onNodeDragStop(end)
  onSelectionDragStart(begin)
  onSelectionDragStop(end)
}
