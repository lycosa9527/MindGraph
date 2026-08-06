import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('sessionRefresh stampede coordinator', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  async function loadSessionRefresh() {
    return import('@/utils/sessionRefresh')
  }

  it('coalesces concurrent refreshSessionAccessToken into one HTTP call', async () => {
    let resolves = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        resolves += 1
        await new Promise((r) => setTimeout(r, 20))
        return new Response(null, { status: 200 })
      })
    )
    const { refreshSessionAccessToken, getSessionRefreshEpoch } = await loadSessionRefresh()
    const epochBefore = getSessionRefreshEpoch()
    const [a, b] = await Promise.all([
      refreshSessionAccessToken(),
      refreshSessionAccessToken(),
    ])
    expect(a).toBe(true)
    expect(b).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(getSessionRefreshEpoch()).toBe(epochBefore + 1)
  })

  it('ensureFreshSessionAfterAuthFailure skips HTTP when epoch already advanced', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 200 }))
    )
    const {
      refreshSessionAccessToken,
      ensureFreshSessionAfterAuthFailure,
      getSessionRefreshEpoch,
    } = await loadSessionRefresh()
    const epochAtStart = getSessionRefreshEpoch()
    expect(await refreshSessionAccessToken()).toBe(true)
    expect(getSessionRefreshEpoch()).toBe(epochAtStart + 1)

    vi.mocked(fetch).mockClear()
    const ok = await ensureFreshSessionAfterAuthFailure(epochAtStart)
    expect(ok).toBe(true)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('ensureFreshSessionAfterAuthFailure refreshes when epoch is unchanged', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 200 }))
    )
    const {
      ensureFreshSessionAfterAuthFailure,
      getSessionRefreshEpoch,
    } = await loadSessionRefresh()
    const epochAtStart = getSessionRefreshEpoch()
    const ok = await ensureFreshSessionAfterAuthFailure(epochAtStart)
    expect(ok).toBe(true)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(getSessionRefreshEpoch()).toBe(epochAtStart + 1)
  })

  it('ensureFreshSessionAfterAuthFailure returns false when refresh fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 401 }))
    )
    const {
      ensureFreshSessionAfterAuthFailure,
      getSessionRefreshEpoch,
    } = await loadSessionRefresh()
    const epochAtStart = getSessionRefreshEpoch()
    const ok = await ensureFreshSessionAfterAuthFailure(epochAtStart)
    expect(ok).toBe(false)
    expect(getSessionRefreshEpoch()).toBe(epochAtStart)
  })

  it('awaitSessionRefreshIdle waits for in-flight refresh', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        await gate
        return new Response(null, { status: 200 })
      })
    )
    const { refreshSessionAccessToken, awaitSessionRefreshIdle, isSessionRefreshInFlight } =
      await loadSessionRefresh()
    const pending = refreshSessionAccessToken()
    expect(isSessionRefreshInFlight()).toBe(true)
    let idleDone = false
    const idle = awaitSessionRefreshIdle().then(() => {
      idleDone = true
    })
    await Promise.resolve()
    expect(idleDone).toBe(false)
    release()
    await pending
    await idle
    expect(idleDone).toBe(true)
  })
})
