/**
 * Account-backed library demo document: lists, notes, and type styles.
 */
import {
  DEMO_CAPTION_STORAGE_KEY,
  type DemoCaptionDraft,
  readDemoCaptionStore,
} from '@/composables/demo/demoCaptionDefaults'
import {
  DEMO_LIST_STORAGE_KEY,
  type DemoListRecord,
  readDemoListStore,
} from '@/composables/demo/demoLists'
import { apiGet, apiPut } from '@/utils/apiClient'

export interface LibraryDemoThumbnail {
  url: string
  updatedAt: string
}

export interface LibraryDemoDocument {
  lists: DemoListRecord[]
  lastId: string | null
  captions: Record<string, DemoCaptionDraft>
  thumbnails: Record<string, LibraryDemoThumbnail>
}

const THUMB_URL = /^\/api\/auth\/library-demo\/thumbnails\/[A-Za-z0-9_-]{1,64}$/

export function parseLibraryDemoThumbnails(raw: unknown): Record<string, LibraryDemoThumbnail> {
  if (!raw || typeof raw !== 'object') return {}
  const thumbnails: Record<string, LibraryDemoThumbnail> = {}
  for (const [id, value] of Object.entries(raw)) {
    if (!THUMB_URL.test(`/api/auth/library-demo/thumbnails/${id}`)) continue
    if (!value || typeof value !== 'object') continue
    const record = value as { url?: unknown; updatedAt?: unknown }
    if (typeof record.updatedAt !== 'string' || Number.isNaN(Date.parse(record.updatedAt))) continue
    const url = typeof record.url === 'string' ? record.url : ''
    if (url !== '' && url !== `/api/auth/library-demo/thumbnails/${id}`) continue
    thumbnails[id] = { url, updatedAt: record.updatedAt }
  }
  return thumbnails
}

export function parseLibraryDemoDocument(raw: unknown): LibraryDemoDocument {
  const record =
    raw && typeof raw === 'object'
      ? (raw as { lists?: unknown; lastId?: unknown; captions?: unknown; thumbnails?: unknown })
      : {}
  const stored = readDemoListStore(
    JSON.stringify({ lists: record.lists ?? [], lastId: record.lastId ?? null })
  )
  return {
    lists: stored.lists,
    lastId: stored.lastId,
    captions: readDemoCaptionStore(JSON.stringify(record.captions ?? {})),
    thumbnails: parseLibraryDemoThumbnails(record.thumbnails),
  }
}

function browserDocument(): LibraryDemoDocument | null {
  const stored = readDemoListStore(localStorage.getItem(DEMO_LIST_STORAGE_KEY))
  const captions = readDemoCaptionStore(localStorage.getItem(DEMO_CAPTION_STORAGE_KEY))
  if (stored.lists.length === 0 && Object.keys(captions).length === 0) return null
  return { lists: stored.lists, lastId: stored.lastId, captions, thumbnails: {} }
}

function clearBrowserDocument(): void {
  localStorage.removeItem(DEMO_LIST_STORAGE_KEY)
  localStorage.removeItem(DEMO_CAPTION_STORAGE_KEY)
}

export async function loadLibraryDemo(): Promise<LibraryDemoDocument> {
  const response = await apiGet('/api/auth/library-demo')
  if (!response.ok) throw new Error('library demo load failed')
  const remote = parseLibraryDemoDocument(await response.json())
  if (remote.lists.length > 0 || Object.keys(remote.captions).length > 0) {
    clearBrowserDocument()
    return remote
  }
  const local = browserDocument()
  if (!local) return remote
  await saveLibraryDemo(local)
  clearBrowserDocument()
  return local
}

export async function saveLibraryDemo(document: LibraryDemoDocument): Promise<void> {
  const response = await apiPut('/api/auth/library-demo', document)
  if (!response.ok) throw new Error('library demo save failed')
}
