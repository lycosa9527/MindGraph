/**
 * Renderers Index
 *
 * The D3.js-based renderers have been replaced with Vue Flow components.
 *
 * New Architecture:
 * - Components: @/components/diagram/ (DiagramCanvas, nodes, edges)
 * - Spec loaders: @/stores/specLoader/
 * - Types: @/types/vueflow.ts (MindGraphNode, MindGraphEdge, etc.)
 *
 * To render diagrams, mount `DiagramCanvas` with diagram data loaded into the diagram store
 * (`useDiagramStore`). The canvas reads `vueFlowNodes` / `vueFlowEdges` from the store; it does
 * not take `:nodes` / `:edges` props.
 *
 * @example
 * ```vue
 * <script setup>
 * import { DiagramCanvas } from '@/components/diagram'
 * import { useDiagramStore } from '@/stores'
 *
 * const diagramStore = useDiagramStore()
 * // Load a spec so diagramStore.data is set.
 * </script>
 *
 * <template>
 *   <DiagramCanvas v-if="diagramStore.data" />
 * </template>
 * ```
 */

// Re-export types
export type {
  MindGraphNode,
  MindGraphEdge,
  MindGraphNodeData,
  MindGraphEdgeData,
} from '@/types/vueflow'
