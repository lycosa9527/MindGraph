import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const useAuthStore = vi.fn()

vi.mock('@/stores/auth', () => ({
  AUTH_USER_STORAGE_KEY: 'auth_user',
  useAuthStore: () => useAuthStore(),
}))

vi.mock('@/stores/ui', () => ({
  useUIStore: () => ({ language: 'en' }),
}))

describe('hasPersistedAuthUser', () => {
  beforeEach(() => {
    sessionStorage.clear()
    useAuthStore.mockReset()
    useAuthStore.mockReturnValue({ user: null })
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  async function loadHelper() {
    const mod = await import('@/utils/apiClient')
    return mod.hasPersistedAuthUser
  }

  it('is false for guests', async () => {
    const hasPersistedAuthUser = await loadHelper()
    expect(hasPersistedAuthUser()).toBe(false)
  })

  it('is true when Pinia has a user', async () => {
    useAuthStore.mockReturnValue({ user: { id: 3 } })
    const hasPersistedAuthUser = await loadHelper()
    expect(hasPersistedAuthUser()).toBe(true)
  })

  it('is true when sessionStorage still has auth_user', async () => {
    sessionStorage.setItem('auth_user', JSON.stringify({ id: 3 }))
    const hasPersistedAuthUser = await loadHelper()
    expect(hasPersistedAuthUser()).toBe(true)
  })
})
