/**
 * Library Store
 *
 * Pinia store for library PDF management and danmaku operations.
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import {
  type LibraryDocument,
  type LibraryDanmaku,
  type LibraryDanmakuReply,
  type CreateDanmakuData,
  type CreateReplyData,
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
} from '@/utils/apiClient'

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

  /**
   * Fetch library documents list
   */
  async function fetchDocuments(page: number = 1, pageSize: number = 20, search?: string) {
    documentsLoading.value = true
    documentsError.value = null
    try {
      const result = await getLibraryDocuments(page, pageSize, search)
      documents.value = result.documents
      documentsTotal.value = result.total
      documentsPage.value = result.page
      documentsPageSize.value = result.page_size
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
    currentDocumentLoading.value = true
    currentDocumentError.value = null
    try {
      currentDocument.value = await getLibraryDocument(documentId)
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
  }
})
