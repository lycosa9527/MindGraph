import { afterEach, describe, expect, it, vi } from 'vitest'

import { enqueueKittyDesktopExplainNode } from '@/composables/kitty/enqueueKittyDesktopExplainNode'

describe('enqueueKittyDesktopExplainNode', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('posts explain_node with node id, label, and library id', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const ok = await enqueueKittyDesktopExplainNode({
      nodeId: 'branch-r-1-0',
      nodeLabel: '广东',
      diagramLibraryId: 'lib-diagram-1',
    })

    expect(ok).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/kitty/desktop_action/enqueue', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'explain_node',
        node_id: 'branch-r-1-0',
        node_label: '广东',
        diagram_library_id: 'lib-diagram-1',
      }),
    })
  })

  it('skips empty node id', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const ok = await enqueueKittyDesktopExplainNode({ nodeId: '  ' })
    expect(ok).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
