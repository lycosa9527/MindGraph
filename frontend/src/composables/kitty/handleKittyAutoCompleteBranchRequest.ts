/**
 * Handle Kitty ``auto_complete_branch`` → mind-map subgraph expand (branch glow)
 * via the verified local commit path (paste → verify → Hub persist).
 */
import {
  generateMindMapSubgraphForNode,
  type MindMapSubgraphPersistOptions,
} from '@/composables/editor/useMindMapSubgraphSuggest'
import { notify } from '@/composables/core/notifications'
import type { DiagramHubPersistDeps } from '@/composables/kitty/diagramEditHubPersist'
import {
  beginQuietBranchComplete,
  endQuietBranchComplete,
} from '@/composables/kitty/kittyQuietBranchCompleteBatch'
import { i18n } from '@/i18n'
import { useDiagramStore } from '@/stores'
import { findMindMapNodeIdByLabel } from '@/utils/findMindMapNodeIdByLabel'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'

export type KittyAutoCompletePersistHooks = {
  ensureConnected: () => Promise<boolean>
  hubPersist: () => DiagramHubPersistDeps
}

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

export async function handleKittyAutoCompleteBranchRequest(
  payload: {
    nodeId?: string
    nodeLabel?: string
  },
  persistHooks?: KittyAutoCompletePersistHooks
): Promise<boolean> {
  const diagramStore = useDiagramStore()
  const t = i18n.global.t.bind(i18n.global) as (key: string) => string

  if (!isMindMapDiagramType(diagramStore.type)) {
    notify.warning(t('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed'))
    return false
  }

  // Coalesce multi-branch Kitty fills into one short "branches ready" chat reply.
  beginQuietBranchComplete()

  const nodeId = await resolveAutoCompleteBranchNodeIdReady(payload)
  if (!nodeId) {
    endQuietBranchComplete(false)
    return false
  }

  let persist: MindMapSubgraphPersistOptions | undefined
  if (persistHooks) {
    const connected = await persistHooks.ensureConnected()
    if (!connected) {
      endQuietBranchComplete(false)
      return false
    }
    persist = {
      hubPersist: persistHooks.hubPersist(),
      requireHubPersist: true,
    }
  }

  return generateMindMapSubgraphForNode(nodeId, {
    persist,
    anchorLabel: payload.nodeLabel,
    // Kitty already acked the turn; canvas glow is enough while fills run.
    // Final chat line is coalesced by kittyQuietBranchCompleteBatch.
    quietSuccess: true,
  })
}
