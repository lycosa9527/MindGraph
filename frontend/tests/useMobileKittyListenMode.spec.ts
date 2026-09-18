import { describe, expect, it } from 'vitest'

import {
  asrCommitModeForListen,
  loadKittyListenMode,
  persistKittyListenMode,
  resolveKittyMicButtonAria,
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

  it('names the icon-only mic from hold / auto state, never painted copy', () => {
    const translate = (_key: string, fallback: string) => fallback
    expect(resolveKittyMicButtonAria('manual', false, false, translate)).toBe('按住说话')
    expect(resolveKittyMicButtonAria('manual', false, true, translate)).toBe('松开发送')
    expect(resolveKittyMicButtonAria('manual', true, false, translate)).toBe('松开发送')
    expect(resolveKittyMicButtonAria('auto', false, false, translate)).toBe('点按开始听')
    expect(resolveKittyMicButtonAria('auto', true, false, translate)).toBe('点按停止')
  })
})
