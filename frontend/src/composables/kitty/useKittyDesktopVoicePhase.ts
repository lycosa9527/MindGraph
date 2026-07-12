/**
 * Desktop canvas: live Kitty mic/reply phase from SSE (drives FAB glow).
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { KittyAgentState } from '@/composables/kitty/kittyAgentTypes'

const VALID_PHASES = new Set<KittyAgentState>(['listening', 'speaking', 'active'])

function normalizePhase(raw: unknown): KittyAgentState | null {
  if (typeof raw !== 'string') {
    return null
  }
  const phase = raw.trim().toLowerCase() as KittyAgentState
  return VALID_PHASES.has(phase) ? phase : null
}

export function useKittyDesktopVoicePhase(options: {
  enabled: ComputedRef<boolean>
  scopeId: Ref<string | null> | ComputedRef<string | null>
}): { phase: Ref<KittyAgentState> } {
  const phase = ref<KittyAgentState>('active')

  function scopeMatches(scope: string | undefined): boolean {
    const current = options.scopeId.value?.trim() ?? ''
    return scope != null && scope.trim() !== '' && current !== '' && scope.trim() === current
  }

  function reset(): void {
    phase.value = 'active'
  }

  function onVoicePhase(payload: { scope?: string; phase?: string }): void {
    if (!options.enabled.value) {
      return
    }
    if (!scopeMatches(payload.scope)) {
      return
    }
    const next = normalizePhase(payload.phase)
    if (next == null) {
      return
    }
    phase.value = next
  }

  eventBus.onWithOwner('kitty:desktop_voice_phase_update', onVoicePhase, 'KittyDesktopVoicePhase')

  watch(
    () => options.enabled.value,
    (on) => {
      if (!on) {
        reset()
      }
    }
  )

  watch(
    () => options.scopeId.value,
    () => {
      reset()
    }
  )

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner('KittyDesktopVoicePhase')
  })

  return { phase }
}
