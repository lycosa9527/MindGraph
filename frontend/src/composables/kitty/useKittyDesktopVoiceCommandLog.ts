/**
 * Desktop canvas: rolling log of mobile Kitty voice commands (SSE fanout).
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { formatKittyVoiceCommandLabel } from '@/composables/kitty/kittyVoiceCommandLabels'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'

export interface KittyDesktopVoiceCommandEntry {
  id: string
  action: string
  label: string
  at: number
}

const MAX_ENTRIES = 8
let entrySeq = 0

export function useKittyDesktopVoiceCommandLog(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): { entries: Ref<KittyDesktopVoiceCommandEntry[]>; clear: () => void } {
  const { t } = useLanguage()
  const entries = ref<KittyDesktopVoiceCommandEntry[]>([])

  function scopeMatches(scope: string | undefined): boolean {
    const current = options.scopeId.value?.trim() ?? ''
    return scope != null && scope.trim() !== '' && current !== '' && scope.trim() === current
  }

  function pushEntry(action: string, detail?: string): void {
    if (!options.enabled.value) {
      return
    }
    const act = action.trim()
    if (!act) {
      return
    }
    entrySeq += 1
    const row: KittyDesktopVoiceCommandEntry = {
      id: `vc-${entrySeq}`,
      action: act,
      label: formatKittyVoiceCommandLabel(act, detail, t),
      at: Date.now(),
    }
    const next = [...entries.value, row]
    entries.value = next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
  }

  function onVoiceCommand(payload: {
    scope?: string
    action?: string
    detail?: string
  }): void {
    if (!options.enabled.value) {
      return
    }
    if (!scopeMatches(payload.scope)) {
      return
    }
    const action = typeof payload.action === 'string' ? payload.action : ''
    const detail = typeof payload.detail === 'string' ? payload.detail : undefined
    pushEntry(action, detail)
  }

  function clear(): void {
    entries.value = []
  }

  eventBus.onWithOwner(
    'kitty:desktop_voice_command',
    onVoiceCommand,
    'KittyDesktopVoiceCommandLog'
  )

  watch(
    () => options.enabled.value,
    (on) => {
      if (!on) {
        clear()
      }
    }
  )

  watch(
    () => options.scopeId.value,
    () => {
      clear()
    }
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('KittyDesktopVoiceCommandLog')
  })

  return { entries, clear }
}
