/**
 * Maite workspace mode binding via event bus.
 */
import { onScopeDispose } from 'vue'
import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useMaiteStore } from '@/stores/maite'

import type { MaiteMode } from '@/types/maite'

export function useMaiteWorkspace() {
  const store = useMaiteStore()
  const { mode, activeSessionId, recentPractice, currentProblemText } = storeToRefs(store)

  const offModeChanged = eventBus.on('maite:mode_changed', ({ mode }) => {
    if (store.mode !== mode) {
      store.setMode(mode)
    }
  })

  function setMode(mode: MaiteMode): void {
    if (store.mode === mode) {
      return
    }
    store.setMode(mode)
    eventBus.emit('maite:mode_changed', { mode })
  }

  onScopeDispose(() => {
    offModeChanged()
  })

  return {
    mode,
    setMode,
    activeSessionId,
    currentProblemText,
    recentPractice,
  }
}
