import { computed, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import {
  beginKittySessionIngress,
  detectScopeDivergence,
  shouldLockDesktopIngressForMobileKitty,
  syncChoicesForDivergence,
} from '@/composables/kitty/useKittySessionManager'
import type { KittySessionSnapshotDto } from '@/composables/kitty/useKittySessionManager'

describe('useKittySessionManager helpers', () => {
  it('locks desktop ingress when snapshot says mobile owns same scope', () => {
    const snap: KittySessionSnapshotDto = {
      user_id: 3,
      requested_scope: 'lib-a',
      desktop_focus_library_id: 'lib-a',
      desktop_focus_updated_at: 1,
      mobile_active: true,
      mobile_scopes: ['lib-a'],
      mobile_primary_scope: 'lib-a',
      canvas_owner_present: true,
      alignment: 'aligned_library',
      ingress_owner: 'mobile',
      error_code: null,
    }
    expect(
      shouldLockDesktopIngressForMobileKitty({
        phase: 'edit',
        diagramScope: 'lib-a',
        mobile: { active: true, scopes: ['lib-a'], primaryScope: 'lib-a' },
        sessionSnapshot: snap,
      })
    ).toBe(true)
    expect(
      shouldLockDesktopIngressForMobileKitty({
        phase: 'create',
        diagramScope: 'lib-a',
        mobile: { active: true, scopes: ['lib-a'], primaryScope: 'lib-a' },
        sessionSnapshot: snap,
      })
    ).toBe(false)
  })

  it('detects scope divergence for A≠B', () => {
    const snap: KittySessionSnapshotDto = {
      user_id: 3,
      requested_scope: 'lib-a',
      desktop_focus_library_id: 'lib-b',
      desktop_focus_updated_at: 1,
      mobile_active: true,
      mobile_scopes: ['lib-a'],
      mobile_primary_scope: 'lib-a',
      canvas_owner_present: false,
      alignment: 'scope_divergence',
      ingress_owner: 'mobile',
      error_code: 'scope_divergence',
    }
    const div = detectScopeDivergence(snap)
    expect(div?.mobileScope).toBe('lib-a')
    expect(div?.desktopScope).toBe('lib-b')
    expect(detectScopeDivergence(null)).toBeNull()
    expect(syncChoicesForDivergence(div).map((c) => c.id)).toEqual([
      'follow_desktop',
      'open_on_desktop',
      'keep_split',
    ])
  })

  it('beginKittySessionIngress stamps request + source for WS send', () => {
    const meta = beginKittySessionIngress({
      requestId: 'req-42',
      source: 'asr',
      text: '加分支',
      utteranceId: 'utt-9',
    })
    expect(meta.requestId).toBe('req-42')
    expect(meta.ingressSource).toBe('asr')
    expect(meta.utteranceId).toBe('utt-9')
  })

  it('locks via sessionSnapshot ingress_owner even when hub mobile list empty', () => {
    const snap: KittySessionSnapshotDto = {
      user_id: 3,
      requested_scope: 'lib-a',
      desktop_focus_library_id: 'lib-a',
      desktop_focus_updated_at: 1,
      mobile_active: true,
      mobile_scopes: ['lib-a'],
      mobile_primary_scope: 'lib-a',
      canvas_owner_present: true,
      alignment: 'aligned_library',
      ingress_owner: 'mobile',
      error_code: null,
    }
    expect(
      shouldLockDesktopIngressForMobileKitty({
        phase: 'edit',
        diagramScope: 'lib-a',
        mobile: { active: false, scopes: [], primaryScope: null },
        sessionSnapshot: snap,
      })
    ).toBe(true)
  })

  it('useKittySessionManager exposes computed alignment refs', async () => {
    const { useKittySessionManager } = await import('@/composables/kitty/useKittySessionManager')
    const scope = ref('lib-a')
    const enabled = computed(() => true)
    const mgr = useKittySessionManager({ scope, enabled })
    expect(mgr.ingressOwner.value).toBe('desktop')
    expect(mgr.divergence.value).toBeNull()
    expect(mgr.syncChoices.value).toEqual([])
  })
})
