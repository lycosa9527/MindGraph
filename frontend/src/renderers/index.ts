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
 * To render diagrams, use the DiagramCanvas component with diagram-specific composables:
 *
 * @example
 * ```vue
 * <script setup>
 * import { DiagramCanvas } from '@/components/diagram'
 * import { useBubbleMap } from '@/composables/diagrams'
 *
 * const bubbleMap = useBubbleMap()
 * bubbleMap.setData({ topic: 'My Topic', attributes: ['Attr 1', 'Attr 2'] })
 * </script>
 *
 * <template>
 *   <DiagramCanvas :nodes="bubbleMap.nodes.value" :edges="bubbleMap.edges.value" />
 * </template>
 * ```
 */

// Re-export diagram composables for backward compatibility
export {
  useBubbleMap,
  useCircleMap,
  useMindMap,
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
