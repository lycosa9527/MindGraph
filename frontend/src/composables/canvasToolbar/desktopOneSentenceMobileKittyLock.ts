/**
 * When Mobile Kitty holds the same diagram scope, desktop one-sentence edit input yields to the phone.
 * Create/generate stays on desktop (mobile cannot run create).
 */
import type { KittyMobileActiveSnapshot } from '@/composables/kitty/kittyDesktopMobileActiveHub'
import { scopeMatchesKittyMobileActive } from '@/composables/kitty/kittyDesktopMobileActiveHub'
import type { OneSentencePhase } from '@/stores/oneSentence'

export function shouldLockDesktopOneSentenceForMobileKitty(options: {
  phase: OneSentencePhase
  diagramScope: string | null | undefined
  mobile: Pick<KittyMobileActiveSnapshot, 'active' | 'scopes' | 'primaryScope'>
}): boolean {
  if (options.phase !== 'edit') {
    return false
  }
  const scope = typeof options.diagramScope === 'string' ? options.diagramScope.trim() : ''
  if (!scope) {
    return false
  }
  return scopeMatchesKittyMobileActive(scope, options.mobile)
}
