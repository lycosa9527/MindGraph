/**
 * On `/m/kitty`, canvas-only voice actions redirect to `/m/canvas` with a pending action.
 */
import { onUnmounted } from 'vue'
import type { Router } from 'vue-router'

import { eventBus } from '@/composables/core/useEventBus'
import { enqueueKittyDesktopExplainNode } from '@/composables/kitty/enqueueKittyDesktopExplainNode'
import {
  consumeKittyPendingCanvasAction,
  stashKittyPendingCanvasAction,
} from '@/composables/kitty/kittyPendingCanvasAction'
import { useDiagramStore } from '@/stores/diagram'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

const OWNER = 'KittyMobileHubActionBridge'

export function useKittyMobileHubActionBridge(router: Router): void {
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  function hasDiagramContext(): boolean {
    return (diagramStore.data?.nodes?.length ?? 0) > 0
  }

  function goCanvasForAction(action: Parameters<typeof stashKittyPendingCanvasAction>[0]): void {
    if (!hasDiagramContext()) {
      return
    }
    stashKittyPendingCanvasAction(action)
    void router.push('/m/canvas')
  }

  eventBus.onWithOwner(
    'kitty:inline_recommendations_requested',
    (data) => {
      goCanvasForAction({
        kind: 'inline_recommendations',
        nodeId: data.nodeId,
        nodeIndex: data.nodeIndex,
      })
    },
    OWNER
  )

  eventBus.onWithOwner(
    'kitty:add_node_with_recommendations_requested',
    (data) => {
      goCanvasForAction({
        kind: 'add_node_with_recommendations',
        text: data.text,
      })
    },
    OWNER
  )

  // Voice explain_node on /m/kitty has no canvas listener — forward to desktop 节点解释.
  eventBus.onWithOwner(
    'mindmap:explain_node_requested',
    (data) => {
      const nodeId = data.nodeId?.trim() ?? ''
      if (!nodeId) {
        return
      }
      void enqueueKittyDesktopExplainNode({
        nodeId,
        diagramLibraryId: savedDiagramsStore.activeDiagramId ?? undefined,
      })
    },
    OWNER
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER)
  })
}

/** Replay a stashed action after navigating to mobile canvas. */
export function replayKittyPendingCanvasAction(): void {
  const pending = consumeKittyPendingCanvasAction()
  if (!pending) {
    return
  }
  if (pending.kind === 'inline_recommendations') {
    eventBus.emit('kitty:inline_recommendations_requested', {
      nodeId: pending.nodeId,
      nodeIndex: pending.nodeIndex,
    })
    return
  }
  eventBus.emit('kitty:add_node_with_recommendations_requested', {
    text: pending.text,
  })
}
