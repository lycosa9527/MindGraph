/**
 * Desktop selection publish posts when Kitty mobile indicator is armed.
 */
import { computed, ref } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

const selectedNodesRef = vi.hoisted(() => {
  // Plain holder; composable reads via getter each watch flush.
  return { value: [] as string[] }
})

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    get selectedNodes() {
      return selectedNodesRef.value
    },
  }),
}))

import { useKittyDesktopSelectionPublish } from '@/composables/kitty/useKittyDesktopSelectionPublish'

describe('useKittyDesktopSelectionPublish', () => {
  beforeEach(() => {
    selectedNodesRef.value = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ ok: true }),
      }))
    )
  })

  it('PUTs selection when enabled and nodes change (via enabled re-arm)', async () => {
    const enabled = ref(false)
    const scopeId = ref<string | null>('lib-diagram-1')
    useKittyDesktopSelectionPublish({
      enabled: computed(() => enabled.value),
      scopeId,
    })

    selectedNodesRef.value = ['node-a']
    enabled.value = true

    await vi.waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/kitty/selection/lib-diagram-1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ selected_nodes: ['node-a'] }),
        })
      )
    })
  })

  it('does not POST when disabled', async () => {
    const enabled = ref(false)
    const scopeId = ref<string | null>('lib-diagram-1')
    useKittyDesktopSelectionPublish({
      enabled: computed(() => enabled.value),
      scopeId,
    })
    selectedNodesRef.value = ['node-b']
    await new Promise((r) => setTimeout(r, 40))
    expect(fetch).not.toHaveBeenCalled()
  })
})
