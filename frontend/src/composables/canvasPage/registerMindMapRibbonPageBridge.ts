/**
 * CanvasPage listeners for ribbon commands that the page already owns.
 */
import { type Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'

export function registerMindMapRibbonPageBridge(options: {
  handleSaveKey: () => void | Promise<void>
  handleSnapshotRecall: (version: number) => void
  handleSnapshotDelete: (version: number) => void
  handleStartPresentationWithTier: () => void | Promise<void>
  handleOpenCollab: (mode: 'organization' | 'network' | 'stop') => void
  handleHandToolToggle: (active: boolean) => void
  handToolActive: Ref<boolean>
}): void {
  eventBus.onWithOwner(
    'canvas:save_requested',
    () => {
      void options.handleSaveKey()
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'snapshot:recall_requested',
    ({ versionNumber }) => {
      options.handleSnapshotRecall(versionNumber)
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'snapshot:delete_requested',
    ({ versionNumber }) => {
      options.handleSnapshotDelete(versionNumber)
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'presentation:start_requested',
    () => {
      void options.handleStartPresentationWithTier()
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'collab:open_requested',
    ({ mode }) => {
      options.handleOpenCollab(mode)
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'view:hand_tool_toggle_requested',
    ({ active }) => {
      options.handleHandToolToggle(active ?? !options.handToolActive.value)
    },
    'CanvasPage'
  )
}
