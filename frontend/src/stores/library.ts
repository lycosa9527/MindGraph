/**
 * Library Store
 *
 * Pinia store for library PDF management and danmaku operations.
 * Includes localStorage caching to reduce server load.
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import {
  type LibraryDocument,
  type LibraryDanmaku,
  type LibraryDanmakuReply,
  type LibraryBookmark,
  type CreateDanmakuData,
  type CreateReplyData,
  type CreateBookmarkData,
  getLibraryDocuments,
  getLibraryDocument,
  getDanmaku,
  createDanmaku,
  likeDanmaku,
  getDanmakuReplies,
  replyToDanmaku,
  deleteDanmaku,
  deleteDanmakuReply,
  updateDanmakuPosition,
  type UpdateDanmakuPositionData,
  getRecentBookmarks,
  createBookmark,
  deleteBookmark,
  getBookmark,
} from '@/utils/apiClient'

// localStorage cache entry with TTL
interface DocumentsCacheEntry {
  documents: LibraryDocument[]
  total: number
  page: number
  page_size: number
  cachedAt: number
}

interface DocumentCacheEntry {
  document: LibraryDocument
  cachedAt: number
}

// Cache TTL: 30 minutes for document list, 1 hour for individual documents
const DOCUMENTS_LIST_CACHE_TTL_MS = 30 * 60 * 1000
const DOCUMENT_CACHE_TTL_MS = 60 * 60 * 1000

// localStorage keys
const DOCUMENTS_LIST_CACHE_KEY_PREFIX = 'library_documents_list_'
const DOCUMENT_CACHE_KEY_PREFIX = 'library_document_'

export const useLibraryStore = defineStore('library', () => {
  // Document list state
  const documents = ref<LibraryDocument[]>([])
  const documentsLoading = ref(false)
  const documentsError = ref<Error | null>(null)
  const documentsTotal = ref(0)
  const documentsPage = ref(1)
  const documentsPageSize = ref(20)

  // Current document state
  const currentDocument = ref<LibraryDocument | null>(null)
  const currentDocumentLoading = ref(false)
  const currentDocumentError = ref<Error | null>(null)

  // Danmaku state
  const danmaku = ref<LibraryDanmaku[]>([])
  const danmakuLoading = ref(false)
  const danmakuError = ref<Error | null>(null)
  const currentPage = ref<number | null>(null)
  const selectedText = ref<string | null>(null)
  const selectedTextBbox = ref<{ x: number; y: number; width: number; height: number } | null>(null)

  // Replies state
  const replies = ref<Record<number, LibraryDanmakuReply[]>>({})
  const repliesLoading = ref<Record<number, boolean>>({})

  // Bookmarks state
  const bookmarks = ref<LibraryBookmark[]>([])
  const bookmarksLoading = ref(false)
  const bookmarksError = ref<Error | null>(null)

  // =========================================================================
  // localStorage Cache Helpers
  // =========================================================================

  /**
   * Get cache key for documents list
   */
  function getDocumentsListCacheKey(page: number, pageSize: number, search?: string): string {
    const searchPart = search ? `_search_${search}` : ''
    return `${DOCUMENTS_LIST_CACHE_KEY_PREFIX}${page}_${pageSize}${searchPart}`
  }

  /**
   * Get cache key for individual document
   */
  function getDocumentCacheKey(documentId: number): string {
    return `${DOCUMENT_CACHE_KEY_PREFIX}${documentId}`
  }

  /**
   * Load documents list from localStorage cache
   */
  function loadDocumentsListFromCache(
    page: number,
    pageSize: number,
    search?: string
  ): DocumentsCacheEntry | null {
    try {
      const key = getDocumentsListCacheKey(page, pageSize, search)
      const stored = localStorage.getItem(key)
      if (!stored) return null

      const entry = JSON.parse(stored) as DocumentsCacheEntry

      // Check TTL
      if (Date.now() - entry.cachedAt > DOCUMENTS_LIST_CACHE_TTL_MS) {
        localStorage.removeItem(key)
        return null
      }

      console.debug(
        `[LibraryStore] Loaded ${entry.documents.length} documents from localStorage cache (page ${page})`
      )
      return entry
    } catch (error) {
      console.debug('[LibraryStore] Failed to load documents list from localStorage:', error)
      return null
    }
  }

  /**
   * Save documents list to localStorage cache
   */
  function saveDocumentsListToCache(
    page: number,
    pageSize: number,
    search: string | undefined,
    documents: LibraryDocument[],
    total: number
  ): void {
    try {
      const key = getDocumentsListCacheKey(page, pageSize, search)
      const entry: DocumentsCacheEntry = {
        documents,
        total,
        page,
        page_size: pageSize,
        cachedAt: Date.now(),
      }
      localStorage.setItem(key, JSON.stringify(entry))
      console.debug(
        `[LibraryStore] Saved ${documents.length} documents to localStorage cache (page ${page})`
      )
    } catch (error) {
      console.debug('[LibraryStore] Failed to save documents list to localStorage:', error)
      // localStorage might be full or disabled - continue without error
    }
  }

  /**
   * Load individual document from localStorage cache
   */
  function loadDocumentFromCache(documentId: number): LibraryDocument | null {
    try {
      const key = getDocumentCacheKey(documentId)
      const stored = localStorage.getItem(key)
      if (!stored) return null

      const entry = JSON.parse(stored) as DocumentCacheEntry

      // Check TTL
      if (Date.now() - entry.cachedAt > DOCUMENT_CACHE_TTL_MS) {
        localStorage.removeItem(key)
        return null
      }

      console.debug(`[LibraryStore] Loaded document ${documentId} from localStorage cache`)
      return entry.document
    } catch (error) {
      console.debug('[LibraryStore] Failed to load document from localStorage:', error)
      return null
    }
  }

  /**
   * Save individual document to localStorage cache
   */
  function saveDocumentToCache(document: LibraryDocument): void {
    try {
      const key = getDocumentCacheKey(document.id)
      const entry: DocumentCacheEntry = {
        document,
        cachedAt: Date.now(),
      }
      localStorage.setItem(key, JSON.stringify(entry))
      console.debug(`[LibraryStore] Saved document ${document.id} to localStorage cache`)
    } catch (error) {
      console.debug('[LibraryStore] Failed to save document to localStorage:', error)
      // localStorage might be full or disabled - continue without error
    }
  }

  /**
   * Clear document cache (when document is updated/deleted)
   */
  function clearDocumentCache(documentId: number): void {
    try {
      const key = getDocumentCacheKey(documentId)
      localStorage.removeItem(key)
      // Also clear from documents list cache (invalidate all list caches)
      for (let i = 0; i < localStorage.length; i++) {
        const cacheKey = localStorage.key(i)
        if (cacheKey && cacheKey.startsWith(DOCUMENTS_LIST_CACHE_KEY_PREFIX)) {
          localStorage.removeItem(cacheKey)
        }
      }
      console.debug(`[LibraryStore] Cleared cache for document ${documentId}`)
    } catch (error) {
      console.debug('[LibraryStore] Failed to clear document cache:', error)
    }
  }

  // =========================================================================
  // API Functions
  // =========================================================================

  /**
   * Fetch library documents list
   */
  async function fetchDocuments(page: number = 1, pageSize: number = 20, search?: string) {
    // Check cache first
    const cached = loadDocumentsListFromCache(page, pageSize, search)
    if (cached) {
      documents.value = cached.documents
      documentsTotal.value = cached.total
      documentsPage.value = cached.page
      documentsPageSize.value = cached.page_size
      return
    }

    documentsLoading.value = true
    documentsError.value = null
    try {
      const result = await getLibraryDocuments(page, pageSize, search)
      documents.value = result.documents
      documentsTotal.value = result.total
      documentsPage.value = result.page
      documentsPageSize.value = result.page_size

      // Save to cache
      saveDocumentsListToCache(page, pageSize, search, result.documents, result.total)
    } catch (error) {
      documentsError.value = error as Error
      console.error('[LibraryStore] Failed to fetch documents:', error)
    } finally {
      documentsLoading.value = false
    }
  }

  /**
   * Fetch a single document
   */
  async function fetchDocument(documentId: number) {
    // Check cache first
    const cached = loadDocumentFromCache(documentId)
    if (cached) {
      currentDocument.value = cached
      return
    }

    currentDocumentLoading.value = true
    currentDocumentError.value = null
    try {
      const document = await getLibraryDocument(documentId)
      currentDocument.value = document

      // Save to cache
      saveDocumentToCache(document)
    } catch (error) {
      currentDocumentError.value = error as Error
      console.error('[LibraryStore] Failed to fetch document:', error)
    } finally {
      currentDocumentLoading.value = false
    }
  }

  /**
   * Fetch danmaku for current document
   */
  async function fetchDanmaku(pageNumber?: number, textSelection?: string) {
    if (!currentDocument.value) {
      return
    }

    danmakuLoading.value = true
    danmakuError.value = null
    currentPage.value = pageNumber || null
    selectedText.value = textSelection || null

    try {
      const result = await getDanmaku(
        currentDocument.value.id,
        pageNumber,
        textSelection
      )
      danmaku.value = result.danmaku
    } catch (error) {
      danmakuError.value = error as Error
      console.error('[LibraryStore] Failed to fetch danmaku:', error)
    } finally {
      danmakuLoading.value = false
    }
  }

  /**
   * Create a danmaku comment
   */
  async function createDanmakuComment(data: CreateDanmakuData) {
    if (!currentDocument.value) {
      throw new Error('No document selected')
    }

    try {
      const result = await createDanmaku(currentDocument.value.id, data)
      // Refresh danmaku list for the page (fetch all, not filtered by text)
      await fetchDanmaku(data.page_number)
      // Update document comments count
      if (currentDocument.value) {
        currentDocument.value.comments_count = (currentDocument.value.comments_count || 0) + 1
        // Update cache
        saveDocumentToCache(currentDocument.value)
      }
      return result.danmaku
    } catch (error) {
      console.error('[LibraryStore] Failed to create danmaku:', error)
      throw error
    }
  }

  /**
   * Toggle like on danmaku
   */
  async function toggleDanmakuLike(danmakuId: number) {
    try {
      const result = await likeDanmaku(danmakuId)
      // Update danmaku in list
      const index = danmaku.value.findIndex((d) => d.id === danmakuId)
      if (index !== -1) {
        danmaku.value[index].is_liked = result.is_liked
        danmaku.value[index].likes_count = result.likes_count
      }
      return result
    } catch (error) {
      console.error('[LibraryStore] Failed to toggle like:', error)
      throw error
    }
  }

  /**
   * Fetch replies for a danmaku
   */
  async function fetchReplies(danmakuId: number) {
    repliesLoading.value[danmakuId] = true
    try {
      const result = await getDanmakuReplies(danmakuId)
      replies.value[danmakuId] = result.replies
    } catch (error) {
      console.error('[LibraryStore] Failed to fetch replies:', error)
    } finally {
      repliesLoading.value[danmakuId] = false
    }
  }

  /**
   * Create a reply to danmaku
   */
  async function createReply(danmakuId: number, data: CreateReplyData) {
    try {
      const result = await replyToDanmaku(danmakuId, data)
      // Refresh replies
      await fetchReplies(danmakuId)
      return result.reply
    } catch (error) {
      console.error('[LibraryStore] Failed to create reply:', error)
      throw error
    }
  }

  /**
   * Update danmaku position
   */
  async function updateDanmakuPos(danmakuId: number, data: UpdateDanmakuPositionData) {
    try {
      await updateDanmakuPosition(danmakuId, data)
      // Update position in local state
      const index = danmaku.value.findIndex((d) => d.id === danmakuId)
      if (index !== -1) {
        if (data.position_x !== undefined) {
          danmaku.value[index].position_x = data.position_x
        }
        if (data.position_y !== undefined) {
          danmaku.value[index].position_y = data.position_y
        }
      }
    } catch (error) {
      console.error('[LibraryStore] Failed to update danmaku position:', error)
      throw error
    }
  }

  /**
   * Delete danmaku
   */
  async function removeDanmaku(danmakuId: number) {
    try {
      await deleteDanmaku(danmakuId)
      // Remove from list
      danmaku.value = danmaku.value.filter((d) => d.id !== danmakuId)
      // Update document comments count
      if (currentDocument.value) {
        currentDocument.value.comments_count = Math.max(
          0,
          currentDocument.value.comments_count - 1
        )
        // Update cache
        saveDocumentToCache(currentDocument.value)
      }
    } catch (error) {
      console.error('[LibraryStore] Failed to delete danmaku:', error)
      throw error
    }
  }

  /**
   * Delete reply
   */
  async function removeReply(replyId: number, danmakuId: number) {
    try {
      await deleteDanmakuReply(replyId)
      // Remove from replies list
      if (replies.value[danmakuId]) {
        replies.value[danmakuId] = replies.value[danmakuId].filter((r) => r.id !== replyId)
      }
    } catch (error) {
      console.error('[LibraryStore] Failed to delete reply:', error)
      throw error
    }
  }

  /**
   * Clear current document state
   */
  function clearCurrentDocument() {
    currentDocument.value = null
    currentDocumentError.value = null
    danmaku.value = []
    currentPage.value = null
    selectedText.value = null
    selectedTextBbox.value = null
    replies.value = {}
  }

  /**
   * Get danmaku for specific page
   */
  const danmakuForPage = computed(() => {
    return (pageNumber: number) => {
      return danmaku.value.filter((d) => d.page_number === pageNumber)
    }
  })

  /**
   * Get danmaku for specific text selection
   */
  const danmakuForText = computed(() => {
    return (text: string) => {
      return danmaku.value.filter(
        (d) => d.selected_text === text && d.text_bbox !== null
      )
    }
  })

  /**
   * Fetch recent bookmarks
   */
  async function fetchRecentBookmarks(limit: number = 50) {
    bookmarksLoading.value = true
    bookmarksError.value = null
    try {
      const result = await getRecentBookmarks(limit)
      bookmarks.value = result.bookmarks
    } catch (error) {
      bookmarksError.value = error as Error
      console.error('[LibraryStore] Failed to fetch bookmarks:', error)
    } finally {
      bookmarksLoading.value = false
    }
  }

  /**
   * Create a bookmark
   */
  async function createBookmarkAction(documentId: number, data: CreateBookmarkData) {
    try {
      const result = await createBookmark(documentId, data)
      // Refresh bookmarks list to include the new bookmark
      await fetchRecentBookmarks()
      return result.bookmark
    } catch (error) {
      console.error('[LibraryStore] Failed to create bookmark:', error)
      throw error
    }
  }

  /**
   * Delete a bookmark
   */
  async function deleteBookmarkAction(bookmarkId: number) {
    try {
      await deleteBookmark(bookmarkId)
      // Remove from list
      bookmarks.value = bookmarks.value.filter((b) => b.id !== bookmarkId)
    } catch (error) {
      console.error('[LibraryStore] Failed to delete bookmark:', error)
      throw error
    }
  }

  /**
   * Get bookmark for a specific document page
   */
  async function getBookmarkAction(documentId: number, pageNumber: number): Promise<LibraryBookmark | null> {
    try {
      return await getBookmark(documentId, pageNumber)
    } catch (error) {
      console.error('[LibraryStore] Failed to get bookmark:', error)
      throw error
    }
  }

  return {
    // Documents
    documents,
    documentsLoading,
    documentsError,
    documentsTotal,
    documentsPage,
    documentsPageSize,
    fetchDocuments,

    // Current document
    currentDocument,
    currentDocumentLoading,
    currentDocumentError,
    fetchDocument,
    clearCurrentDocument,

    // Danmaku
    danmaku,
    danmakuLoading,
    danmakuError,
    currentPage,
    selectedText,
    selectedTextBbox,
    fetchDanmaku,
    createDanmakuComment,
    toggleDanmakuLike,
    updateDanmakuPosition: updateDanmakuPos,
    removeDanmaku,
    danmakuForPage,
    danmakuForText,

    // Replies
    replies,
    repliesLoading,
    fetchReplies,
    createReply,
    removeReply,

    // Bookmarks
    bookmarks,
    bookmarksLoading,
    bookmarksError,
    fetchRecentBookmarks,
    createBookmark: createBookmarkAction,
    deleteBookmark: deleteBookmarkAction,
    getBookmark: getBookmarkAction,
  }
})
