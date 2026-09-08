import { describe, expect, it } from 'vitest'

import {
  hasWorkshopInitializedThisSession,
  markWorkshopInitializedThisSession,
  workshopInitFlagKey,
} from '@/utils/workshopInitializeOnce'

function memoryStorage(): Storage {
  const data = new Map<string, string>()
  return {
    get length() {
      return data.size
    },
    clear() {
      data.clear()
    },
    getItem(key: string) {
      return data.get(key) ?? null
    },
    key() {
      return null
    },
    removeItem(key: string) {
      data.delete(key)
    },
    setItem(key: string, value: string) {
      data.set(key, value)
    },
  }
}

describe('workshopInitializeOnce', () => {
  it('does not skip initialize until a successful flag is stored', () => {
    const storage = memoryStorage()
    expect(hasWorkshopInitializedThisSession(storage, 7)).toBe(false)
    markWorkshopInitializedThisSession(storage, 7)
    expect(storage.getItem(workshopInitFlagKey(7))).toBe('1')
    expect(hasWorkshopInitializedThisSession(storage, 7)).toBe(true)
  })

  it('does not treat a missing user as already initialized', () => {
    const storage = memoryStorage()
    expect(hasWorkshopInitializedThisSession(storage, null)).toBe(false)
    expect(hasWorkshopInitializedThisSession(storage, undefined)).toBe(false)
  })
})
