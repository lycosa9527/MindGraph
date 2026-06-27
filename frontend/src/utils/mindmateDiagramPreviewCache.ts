/** Persist MindMate generate_dingtalk preview PNGs in IndexedDB (survives server temp cleanup). */

const DB_NAME = 'mg_mindmate_preview_v1'
const STORE_NAME = 'previews'
const DB_VERSION = 1
/** Local preview retention (server temp_images cleanup is 24h). */
export const MINDMATE_PREVIEW_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000

interface PreviewCacheRow {
  savedAt: number
  blob: Blob
}

const DINGTALK_PREVIEW_FILENAME_RE = /\/temp_images\/(dingtalk_[a-f0-9]{8}_\d+\.png)/i

/** Stable cache key from assistant markdown (full dingtalk_*.png filename). */
export function extractMindmatePreviewCacheKey(content: string): string | null {
  const match = DINGTALK_PREVIEW_FILENAME_RE.exec((content || '').trim())
  return match?.[1]?.toLowerCase() ?? null
}

function openPreviewDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('indexedDB unavailable'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onerror = () => reject(request.error ?? new Error('indexedDB open failed'))
    request.onsuccess = () => resolve(request.result)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
  })
}

function readRow(db: IDBDatabase, cacheKey: string): Promise<PreviewCacheRow | null> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const request = store.get(cacheKey)
    request.onerror = () => reject(request.error ?? new Error('indexedDB read failed'))
    request.onsuccess = () => {
      const row = request.result as PreviewCacheRow | undefined
      resolve(row ?? null)
    }
  })
}

function writeRow(db: IDBDatabase, cacheKey: string, row: PreviewCacheRow): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.put(row, cacheKey)
    request.onerror = () => reject(request.error ?? new Error('indexedDB write failed'))
    request.onsuccess = () => resolve()
  })
}

function deleteRow(db: IDBDatabase, cacheKey: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.delete(cacheKey)
    request.onerror = () => reject(request.error ?? new Error('indexedDB delete failed'))
    request.onsuccess = () => resolve()
  })
}

/** Read a cached preview PNG blob, or null when missing / expired / unavailable. */
export async function readMindmateDiagramPreview(cacheKey: string): Promise<Blob | null> {
  if (!cacheKey) {
    return null
  }
  try {
    const db = await openPreviewDb()
    try {
      const row = await readRow(db, cacheKey)
      if (!row?.blob || typeof row.savedAt !== 'number') {
        return null
      }
      if (Date.now() - row.savedAt > MINDMATE_PREVIEW_CACHE_TTL_MS) {
        try {
          await deleteRow(db, cacheKey)
        } catch {
          /* best-effort prune */
        }
        return null
      }
      return row.blob
    } finally {
      db.close()
    }
  } catch {
    return null
  }
}

/** Store a preview PNG blob keyed by dingtalk temp filename. */
export async function writeMindmateDiagramPreview(cacheKey: string, blob: Blob): Promise<void> {
  if (!cacheKey || !blob.size) {
    return
  }
  try {
    const db = await openPreviewDb()
    try {
      await writeRow(db, cacheKey, { savedAt: Date.now(), blob })
    } finally {
      db.close()
    }
  } catch {
    /* quota / private mode */
  }
}

/** Remove all locally cached MindMate diagram previews (e.g. on logout). */
export async function clearMindmateDiagramPreviewCache(): Promise<void> {
  if (typeof indexedDB === 'undefined') {
    return
  }
  try {
    const db = await openPreviewDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const request = store.clear()
      request.onerror = () => reject(request.error ?? new Error('indexedDB clear failed'))
      request.onsuccess = () => resolve()
    })
    db.close()
  } catch {
    /* ignore */
  }
}
