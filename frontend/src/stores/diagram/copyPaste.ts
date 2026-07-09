import { computed, ref } from 'vue'

import type { MindMapBranchSpec } from '@/utils/mindMapSubgraphMerge'

import { extractHierarchicalClipboard } from './hierarchicalClipboardExtract'
import {
  pasteHierarchicalClipboard,
  type HierarchicalClipboardPasteDeps,
} from './hierarchicalClipboardPaste'
import type { HierarchicalClipboard } from './hierarchicalClipboardTypes'
import type { DiagramContext } from './types'

export type CopyPasteDeleteDeps = {
  removeMindMapNodes: (nodeIds: string[]) => number
  removeTreeMapNodes: (nodeIds: string[]) => number
  removeBraceMapNodes: (nodeIds: string[]) => number
  removeNode: (nodeId: string) => boolean
  pasteMindMapClipboardBranches: (
    anchorNodeId: string,
    branches: MindMapBranchSpec[],
    historyLabel?: string
  ) => boolean
}

export function useCopyPasteSlice(
  ctx: DiagramContext,
  deps: CopyPasteDeleteDeps
) {
  const { data, selectedNodes, copiedNodes } = ctx
  const hierarchicalClipboard = ref<HierarchicalClipboard | null>(null)

  const canPaste = computed(() => hierarchicalClipboard.value !== null)

  const pasteDeps: HierarchicalClipboardPasteDeps = {
    pasteMindMapClipboardBranches: deps.pasteMindMapClipboardBranches,
  }

  function resolveCopyNodeIds(explicitNodeIds?: string[]): string[] {
    if (explicitNodeIds && explicitNodeIds.length > 0) {
      return explicitNodeIds
    }
    return [...selectedNodes.value]
  }

  function copySelectedNodes(explicitNodeIds?: string[]): boolean {
    if (!data.value?.nodes || !ctx.type.value) return false
    const nodeIds = resolveCopyNodeIds(explicitNodeIds)
    if (nodeIds.length === 0) return false

    const clip = extractHierarchicalClipboard({
      diagramType: ctx.type.value,
      data: data.value,
      nodeIds,
      getMindMapDescendantIds: ctx.getMindMapDescendantIds,
      getTreeMapDescendantIds: ctx.getTreeMapDescendantIds,
    })
    if (!clip) return false

    hierarchicalClipboard.value = clip
    if (clip.payload.kind === 'flat_nodes') {
      copiedNodes.value = clip.payload.nodes
    } else {
      copiedNodes.value = []
    }
    return true
  }

  function cutSelectedNodes(explicitNodeIds?: string[]): boolean {
    if (!copySelectedNodes(explicitNodeIds)) return false
    const clip = hierarchicalClipboard.value
    if (!clip) return false
    deleteNodesForClipboard(clip.sourceNodeIds)
    return true
  }

  function deleteNodesForClipboard(nodeIds: string[]): void {
    const diagramType = ctx.type.value
    if (!diagramType) return

    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      deps.removeMindMapNodes(nodeIds.filter((id) => id.startsWith('branch-')))
      return
    }
    if (diagramType === 'tree_map') {
      deps.removeTreeMapNodes(nodeIds)
      return
    }
    if (diagramType === 'brace_map') {
      deps.removeBraceMapNodes(nodeIds)
      return
    }
    if (diagramType === 'flow_map') {
      nodeIds.forEach((id) => {
        deps.removeNode(id)
      })
      return
    }

    nodeIds.forEach((id) => {
      deps.removeNode(id)
    })
  }

  function pasteClipboardAt(options: {
    anchorNodeId?: string
    flowPosition?: { x: number; y: number }
  }): boolean {
    const clip = hierarchicalClipboard.value
    if (!clip || !ctx.type.value) return false

    return pasteHierarchicalClipboard(ctx, pasteDeps, clip, options)
  }

  function pasteNodesAt(flowPosition: { x: number; y: number }): void {
    pasteClipboardAt({ flowPosition })
  }

  function clearCopiedNodes(): void {
    hierarchicalClipboard.value = null
    copiedNodes.value = []
  }

  return {
    hierarchicalClipboard,
    canPaste,
    copySelectedNodes,
    cutSelectedNodes,
    pasteClipboardAt,
    pasteNodesAt,
    clearCopiedNodes,
  }
}
