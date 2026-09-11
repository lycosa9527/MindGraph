import { describe, expect, it } from 'vitest'

import {
  asrCommitModeForListen,
  loadKittyListenMode,
  persistKittyListenMode,
} from '@/composables/mobile/useMobileKittyListenMode'

describe('useMobileKittyListenMode helpers', () => {
  it('defaults to manual PTT and maps auto to Fun-ASR final commit', () => {
    persistKittyListenMode('manual')
    expect(loadKittyListenMode()).toBe('manual')
    expect(asrCommitModeForListen('manual')).toBe('release_only')
    persistKittyListenMode('auto')
    expect(loadKittyListenMode()).toBe('auto')
    expect(asrCommitModeForListen('auto')).toBe('final_or_stopped')
  })
})
