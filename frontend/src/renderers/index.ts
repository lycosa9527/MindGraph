/**
 * Renderers Index
 *
 * The D3.js-based renderers have been replaced with Vue Flow components.
 *
 * New Architecture:
 * - Components: @/components/diagram/ (DiagramCanvas, nodes, edges)
 * - Composables: @/composables/diagrams/ (useBubbleMap, useCircleMap, etc.)
 * - Types: @/types/vueflow.ts (MindGraphNode, MindGraphEdge, etc.)
 *
 * To render diagrams, mount `DiagramCanvas` with diagram data loaded into the diagram store
 * (`useDiagramStore`). The canvas reads `vueFlowNodes` / `vueFlowEdges` from the store; it does
 * not take `:nodes` / `:edges` props. Diagram-type composables under `@/composables/diagrams`
 * update that store.
 *
 * @example
 * ```vue
 * <script setup>
 * import { DiagramCanvas } from '@/components/diagram'
 * import { useDiagramStore } from '@/stores'
 *
 * const diagramStore = useDiagramStore()
 * // Load a spec or use diagram composables so diagramStore.data is set.
 * </script>
 *
 * <template>
 *   <DiagramCanvas v-if="diagramStore.data" />
 * </template>
 * ```
 */

// Re-export diagram composables for backward compatibility
export {
  useBubbleMap,
  useCircleMap,
  useTreeMap,
  useFlowMap,
  useBraceMap,
  useBridgeMap,
} from '@/composables/diagrams'

// Re-export types
export type {
  MindGraphNode,
  MindGraphEdge,
  MindGraphNodeData,
  MindGraphEdgeData,
} from '@/types/vueflow'
