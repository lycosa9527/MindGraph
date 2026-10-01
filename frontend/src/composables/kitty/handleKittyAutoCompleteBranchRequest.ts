/**
 * Handle Kitty ``auto_complete_branch`` → mind-map subgraph expand (branch glow)
 * via the verified local commit path (paste → verify → Hub persist).
 */
import { notify } from '@/composables/core/notifications'
import { eventBus } from '@/composables/core/useEventBus'
import {
  type MindMapSubgraphPersistOptions,
  generateMindMapSubgraphForNode,
} from '@/composables/editor/useMindMapSubgraphSuggest'
import type { DiagramHubPersistDeps } from '@/composables/kitty/diagramEditHubPersist'
import {
  beginQuietBranchComplete,
  endQuietBranchComplete,
} from '@/composables/kitty/kittyQuietBranchCompleteBatch'
import { useDiagramStore } from '@/stores'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'
import { findMindMapNodeIdByLabel } from '@/utils/findMindMapNodeIdByLabel'

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
    quietChat?: boolean
  },
  persistHooks?: KittyAutoCompletePersistHooks
): Promise<boolean> {
  const diagramStore = useDiagramStore()

  if (!isMindMapDiagramType(diagramStore.type)) {
    notify.warningKey('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed')
    eventBus.emit('kitty:auto_complete_observe', {
      status: 'failed',
      action: 'auto_complete_branch',
    })
    return false
  }

  // Background fills coalesce one FE chat line. User-asked fills stay silent
  // here — the server speaks a single job-done ack after observe.
  const quietChat = payload.quietChat === true
  if (quietChat) {
    beginQuietBranchComplete()
  }

  const nodeId = await resolveAutoCompleteBranchNodeIdReady(payload)
  if (!nodeId) {
    if (quietChat) {
      endQuietBranchComplete(false)
    }
    eventBus.emit('kitty:auto_complete_observe', {
      status: 'failed',
      action: 'auto_complete_branch',
    })
    return false
  }

  let persist: MindMapSubgraphPersistOptions | undefined
  if (persistHooks) {
    const connected = await persistHooks.ensureConnected()
    if (!connected) {
      if (quietChat) {
        endQuietBranchComplete(false)
      }
      eventBus.emit('kitty:auto_complete_observe', {
        status: 'failed',
        nodeId,
        action: 'auto_complete_branch',
      })
      return false
    }
    persist = {
      hubPersist: persistHooks.hubPersist(),
      requireHubPersist: true,
    }
  }

  const ok = await generateMindMapSubgraphForNode(nodeId, {
    persist,
    anchorLabel: payload.nodeLabel,
    // Glow only while filling. User-asked done line is the server ack;
    // background fills use kittyQuietBranchCompleteBatch.
    quietSuccess: true,
  })
  eventBus.emit('kitty:auto_complete_observe', {
    status: ok ? 'finished' : 'failed',
    nodeId,
    action: 'auto_complete_branch',
  })
  return ok
}
