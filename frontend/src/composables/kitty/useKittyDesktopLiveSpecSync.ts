/**
 * @deprecated Use `useKittyDesktopRemoteSync` — selection-only slice retained for tests.
 */
import { type ComputedRef, type Ref } from 'vue'

import { useKittyDesktopRemoteSync } from '@/composables/kitty/useKittyDesktopRemoteSync'

export function useKittyDesktopLiveSpecSync(options: {
  libraryDiagramId: Ref<string | null> | ComputedRef<string | null>
  syncEnabled: ComputedRef<boolean>
  collabSessionActive: ComputedRef<boolean>
}) {
  return useKittyDesktopRemoteSync(options)
}
