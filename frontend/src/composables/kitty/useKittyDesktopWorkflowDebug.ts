/**
 * Rolling Kitty workflow trace log for desktop canvas (paired mobile session).
 */
import { type ComputedRef, type Ref, onUnmounted, ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { KittyWorkflowTracePayload } from '@/composables/kitty/kittyWorkflowTrace'

export interface KittyDesktopWorkflowEntry {
  id: string
  lane: string
  stage: string
  detail: string
  at: number
}

const MAX_ENTRIES = 48

export function useKittyDesktopWorkflowDebug(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): { entries: Ref<KittyDesktopWorkflowEntry[]> } {
  const entries = ref<KittyDesktopWorkflowEntry[]>([])
  let seq = 0

  function scopeMatches(scope?: string): boolean {
    const current = options.scopeId.value?.trim() ?? ''
    if (!current) {
      return true
    }
    if (!scope?.trim()) {
      return true
    }
    return scope.trim() === current
  }

  function pushEntry(payload: KittyWorkflowTracePayload): void {
    if (!options.enabled.value) {
      return
    }
    if (!scopeMatches(payload.scope)) {
      return
    }
    seq += 1
    const row: KittyDesktopWorkflowEntry = {
      id: `wf-${seq}-${payload.at}`,
      lane: payload.lane,
      stage: payload.stage,
      detail: payload.detail,
      at: payload.at,
    }
    entries.value = [row, ...entries.value].slice(0, MAX_ENTRIES)
  }

  eventBus.onWithOwner(
    'kitty:workflow_trace',
    (payload) => {
      pushEntry(payload)
    },
    'KittyDesktopWorkflowDebug'
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('KittyDesktopWorkflowDebug')
  })

  return { entries }
}
