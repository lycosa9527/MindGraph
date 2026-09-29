/**
 * Named demo playlists saved in this browser.
 * Each list keeps the caption text and type style for its diagrams.
 */
import {
  type DemoCaptionDraft,
  parseStoredDemoCaption,
} from '@/composables/demo/demoCaptionDefaults'

export const DEMO_LIST_STORAGE_KEY = 'mg.libraryDemo.lists.v1'

export interface DemoListRecord {
  id: string
  name: string
  diagramIds: string[]
  captions: Record<string, DemoCaptionDraft>
}

export interface DemoListStore {
  lists: DemoListRecord[]
  lastId: string | null
}

function parseList(value: unknown): DemoListRecord | null {
  if (!value || typeof value !== 'object') return null
  const record = value as {
    id?: unknown
    name?: unknown
    diagramIds?: unknown
    captions?: unknown
  }
  if (typeof record.id !== 'string' || !record.id) return null
  if (typeof record.name !== 'string' || !record.name.trim()) return null
  if (!Array.isArray(record.diagramIds)) return null
  const diagramIds = record.diagramIds.filter(
    (id): id is string => typeof id === 'string' && id.length > 0
  )
  const captions: Record<string, DemoCaptionDraft> = {}
  if (record.captions && typeof record.captions === 'object') {
    for (const [id, caption] of Object.entries(record.captions)) {
      const draft = parseStoredDemoCaption(caption)
      if (draft) captions[id] = draft
    }
  }
  return { id: record.id, name: record.name.trim(), diagramIds, captions }
}

export function readDemoListStore(raw: string | null): DemoListStore {
  if (!raw) return { lists: [], lastId: null }
  try {
    const parsed = JSON.parse(raw) as { lists?: unknown; lastId?: unknown }
    const lists = Array.isArray(parsed.lists)
      ? parsed.lists.map(parseList).filter((list): list is DemoListRecord => list !== null)
      : []
    const lastId = typeof parsed.lastId === 'string' ? parsed.lastId : null
    return { lists, lastId: lists.some((list) => list.id === lastId) ? lastId : null }
  } catch {
    return { lists: [], lastId: null }
  }
}

export function upsertDemoList(store: DemoListStore, list: DemoListRecord): DemoListStore {
  const lists = store.lists.filter((item) => item.id !== list.id)
  lists.push(list)
  return { lists, lastId: list.id }
}
