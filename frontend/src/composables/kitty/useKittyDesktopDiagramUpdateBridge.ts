/**
 * @deprecated Use `useKittyDesktopRemoteSync` — diagram fanout is handled there.
 */
import { type ComputedRef } from 'vue'

import { useKittyDesktopRemoteSync } from '@/composables/kitty/useKittyDesktopRemoteSync'

export function useKittyDesktopDiagramUpdateBridge(options: {
  libraryDiagramId: ComputedRef<string | null>
  syncEnabled: ComputedRef<boolean>
  collabSessionActive?: ComputedRef<boolean>
}): void {
  useKittyDesktopRemoteSync({
    libraryDiagramId: options.libraryDiagramId,
    syncEnabled: options.syncEnabled,
    collabSessionActive: options.collabSessionActive ?? options.syncEnabled,
  })
}
