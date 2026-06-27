import { beforeEach, vi } from 'vitest'

const memoryStore = new Map<string, string>()

function createStorage(): Storage {
  return {
    get length() {
      return memoryStore.size
    },
    clear() {
      memoryStore.clear()
    },
    getItem(key: string) {
      return memoryStore.get(key) ?? null
    },
    key(index: number) {
      return [...memoryStore.keys()][index] ?? null
    },
    removeItem(key: string) {
      memoryStore.delete(key)
    },
    setItem(key: string, value: string) {
      memoryStore.set(key, value)
    },
  }
}

beforeEach(() => {
  memoryStore.clear()
  vi.stubGlobal('localStorage', createStorage())
  vi.stubGlobal('sessionStorage', createStorage())
})
