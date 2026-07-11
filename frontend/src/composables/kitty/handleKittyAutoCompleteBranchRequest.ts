/**
 * Handle Kitty ``auto_complete_branch`` → mind-map subgraph expand (branch glow).
 */
import { generateMindMapSubgraphForNode } from '@/composables/editor/useMindMapSubgraphSuggest'
import { eventBus } from '@/composables/core/useEventBus'
import { notify } from '@/composables/core/notifications'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores'
import { findMindMapNodeIdByLabel } from '@/utils/findMindMapNodeIdByLabel'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'

function resolveAutoCompleteBranchNodeId(payload: {
  nodeId?: string
  nodeLabel?: string
}): string | null {
  const diagramStore = useDiagramStore()
  const nodes = diagramStore.data?.nodes
  const connections = diagramStore.data?.connections
  let nodeId =
    typeof payload.nodeId === 'string' && payload.nodeId.trim() !== ''
      ? payload.nodeId.trim()
      : null
  // Post-add Kitty commands often set node_id to the label text; only trust real ids.
  if (nodeId && !nodes?.some((node) => node.id === nodeId)) {
    nodeId = null
  }
  if (!nodeId && payload.nodeLabel) {
    nodeId = findMindMapNodeIdByLabel(nodes, connections, payload.nodeLabel)
  }
  return nodeId
}

async function resolveAutoCompleteBranchNodeIdReady(payload: {
  nodeId?: string
  nodeLabel?: string
}): Promise<string | null> {
  // Parallel add_node + auto_complete_branch: wait for the new branch to land.
  for (let attempt = 0; attempt < 25; attempt += 1) {
    const nodeId = resolveAutoCompleteBranchNodeId(payload)
    if (nodeId) {
      return nodeId
    }
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 80)
    })
  }
  return null
}

export async function handleKittyAutoCompleteBranchRequest(payload: {
  nodeId?: string
  nodeLabel?: string
}): Promise<boolean> {
  const diagramStore = useDiagramStore()
  const t = i18n.global.t.bind(i18n.global) as (key: string) => string

  if (!isMindMapDiagramType(diagramStore.type)) {
    notify.warning(t('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed'))
    return false
  }

  const nodeId = await resolveAutoCompleteBranchNodeIdReady(payload)
  if (!nodeId) {
    notify.warning(t('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed'))
    eventBus.emit('kitty:diagram_edit_failed', {
      action: 'auto_complete_branch',
      errorCode: 'branch_not_found',
      message: payload.nodeLabel,
      scope: null,
    })
    eventBus.emit('kitty:diagram_action_completed', {
      action: 'auto_complete_branch',
      ok: false,
      errorCode: 'branch_not_found',
    })
    return false
  }

  return generateMindMapSubgraphForNode(nodeId)
}
