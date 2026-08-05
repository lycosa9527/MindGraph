import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  MINDMAP_CANVAS_MODE_KEY,
  MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY,
  ensureMindMapCanvasV2DefaultMigration,
  useUIStore,
} from '@/stores/ui'

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const map = new Map<string, string>(Object.entries(initial))
  return {
    get length() {
      return map.size
    },
    clear() {
      map.clear()
    },
    getItem(key: string) {
      return map.has(key) ? (map.get(key) as string) : null
    },
    key(index: number) {
      return Array.from(map.keys())[index] ?? null
    },
    removeItem(key: string) {
      map.delete(key)
    },
    setItem(key: string, value: string) {
      map.set(key, value)
    },
  }
}

describe('ensureMindMapCanvasV2DefaultMigration', () => {
  it('forces v2 and stamps migration when Classic was stored', () => {
    const storage = memoryStorage({ [MINDMAP_CANVAS_MODE_KEY]: 'legacy' })
    ensureMindMapCanvasV2DefaultMigration(storage)
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('v2')
    expect(storage.getItem(MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY)).toBe('1')
  })

  it('is a no-op after migration when user later chooses Classic', () => {
    const storage = memoryStorage({
      [MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY]: '1',
      [MINDMAP_CANVAS_MODE_KEY]: 'legacy',
    })
    ensureMindMapCanvasV2DefaultMigration(storage)
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('legacy')
  })

  it('stamps migration when no prior canvas mode exists', () => {
    const storage = memoryStorage()
    ensureMindMapCanvasV2DefaultMigration(storage)
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('v2')
    expect(storage.getItem(MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY)).toBe('1')
  })
})

describe('setMindMapCanvasMode persist flag', () => {
  let storage: Storage

  beforeEach(() => {
    storage = memoryStorage({
      [MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY]: '1',
      [MINDMAP_CANVAS_MODE_KEY]: 'v2',
    })
    vi.stubGlobal('localStorage', storage)
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('does not overwrite saved New canvas when Classic is runtime-only', () => {
    const uiStore = useUIStore()
    expect(uiStore.mindMapCanvasMode).toBe('v2')
    uiStore.setMindMapCanvasMode('legacy', { persist: false })
    expect(uiStore.mindMapCanvasMode).toBe('legacy')
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('v2')
  })

  it('persists Classic when the user explicitly opts in', () => {
    const uiStore = useUIStore()
    uiStore.setMindMapCanvasMode('legacy')
    expect(uiStore.mindMapCanvasMode).toBe('legacy')
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('legacy')
  })

  it('persists Classic opt-in even when memory was already runtime Classic', () => {
    const uiStore = useUIStore()
    uiStore.setMindMapCanvasMode('legacy', { persist: false })
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('v2')
    uiStore.setMindMapCanvasMode('legacy')
    expect(storage.getItem(MINDMAP_CANVAS_MODE_KEY)).toBe('legacy')
  })
})
