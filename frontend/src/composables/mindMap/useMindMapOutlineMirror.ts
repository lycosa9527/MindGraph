import { computed, nextTick, ref, watch } from 'vue'

import { isMindMapPathCollapsed } from '@/stores/diagram/mindMapCollapse'
import { useDiagramStore } from '@/stores'
import {
  buildMindMapOutlineTree,
  type MindMapOutlineNode,
} from '@/utils/mindMapOutlineTree'

/** Collect ancestor node ids from root to target (exclusive of target). */
export function getMindMapAncestorIds(
  nodeId: string,
  connections: Array<{ source: string; target: string }>
): string[] {
  const ancestors: string[] = []
  let current: string | undefined = nodeId
  while (current && current !== 'topic') {
    const parent = connections.find((c) => c.target === current)?.source
    if (!parent) break
    ancestors.unshift(parent)
    current = parent
  }
  return ancestors
}

/**
 * Keep 层级大纲 mirrored with the live diagram: structure, labels, canvas Y order,
 * selection, and branch collapse.
 */
export function useMindMapOutlineMirror(options: {
  enabled: () => boolean
  scrollToRow: (nodeId: string) => void
}) {
  const diagramStore = useDiagramStore()
  const syncingFromOutline = ref(false)

  /** Reactive tree — tracks text, topology, and positions used for canvas-Y ordering. */
  const outlineTree = computed((): MindMapOutlineNode[] => {
    const nodes = diagramStore.data?.nodes ?? []
    const connections = diagramStore.data?.connections ?? []
    for (const node of nodes) {
      void node.id
      void node.text
      void node.position?.y
      void (node.data as { label?: string } | undefined)?.label
    }
    for (const conn of connections) {
      void conn.id
      void conn.source
      void conn.target
    }
    return buildMindMapOutlineTree(nodes, connections)
  })

  function isOutlineBranchCollapsed(nodeId: string): boolean {
    const connections = diagramStore.data?.connections ?? []
    const paths = diagramStore.data?._collapsed_paths ?? []
    return isMindMapPathCollapsed(nodeId, connections, paths)
  }

  function focusNodeFromCanvas(nodeId: string): void {
    if (!options.enabled() || syncingFromOutline.value) return
    diagramStore.expandMindMapPathToNode(nodeId)
    void nextTick(() => options.scrollToRow(nodeId))
  }

  function focusNodeFromOutline(nodeId: string): void {
    syncingFromOutline.value = true
    diagramStore.expandMindMapPathToNode(nodeId)
    diagramStore.selectNodes(nodeId)
    void nextTick(() => {
      options.scrollToRow(nodeId)
      syncingFromOutline.value = false
    })
  }

  /** Sync with canvas mind-map branch collapse (_collapsed_paths). */
  function toggleOutlineBranch(nodeId: string): void {
    diagramStore.toggleMindMapCollapse(nodeId)
  }

  watch(
    () => [...diagramStore.selectedNodes],
    (ids) => {
      if (syncingFromOutline.value) return
      const nodeId = ids[0]
      if (!nodeId || !options.enabled()) return
      focusNodeFromCanvas(nodeId)
    }
  )

  return {
    outlineTree,
    focusNodeFromOutline,
    toggleOutlineBranch,
    isOutlineBranchCollapsed,
    getOutlineTree: (): MindMapOutlineNode[] => outlineTree.value,
  }
}
