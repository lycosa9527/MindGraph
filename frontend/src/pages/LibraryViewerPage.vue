<script setup lang="ts">
/**
 * LibraryViewerPage - PDF viewer with danmaku and comments
 * Combines PdfViewer, DanmakuOverlay, and CommentPanel components
 */
import { onMounted, onUnmounted, computed, watch, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElButton, ElIcon } from 'element-plus'
import { ArrowLeft } from 'lucide-vue-next'

import { useLibraryStore } from '@/stores/library'
import { useNotifications, useLanguage } from '@/composables'
import { getLibraryDocumentFileUrl, createBookmark, getBookmark, deleteBookmark, type CreateBookmarkData } from '@/utils/apiClient'

import PdfViewer from '@/components/library/PdfViewer.vue'
import PdfToolbar from '@/components/library/PdfToolbar.vue'
import DanmakuOverlay from '@/components/library/DanmakuOverlay.vue'
import CommentPanel from '@/components/library/CommentPanel.vue'

const route = useRoute()
const router = useRouter()
const libraryStore = useLibraryStore()
const notify = useNotifications()
const { isZh } = useLanguage()

const pdfViewerRef = ref<InstanceType<typeof PdfViewer> | null>(null)

const documentId = computed(() => parseInt(route.params.id as string))
const pdfUrl = computed(() => {
  if (!libraryStore.currentDocument) return ''
  return getLibraryDocumentFileUrl(libraryStore.currentDocument.id)
})

const currentPage = computed(() => pdfViewerRef.value?.currentPage || 1)
const totalPages = computed(() => pdfViewerRef.value?.totalPages || 0)
const zoom = computed(() => pdfViewerRef.value?.zoom || 1.0)
const pinMode = computed(() => pdfViewerRef.value?.pinMode ?? false)
const canGoPrevious = computed(() => currentPage.value > 1)
const canGoNext = computed(() => currentPage.value < totalPages.value)

// Pin/comment state
const selectedDanmakuId = ref<number | null>(null)
const pinPlacementPosition = ref<{ x: number; y: number; pageNumber: number } | null>(null)

// Get danmaku for current page
const currentPageDanmaku = computed(() => {
  return libraryStore.danmaku.filter((d) => d.page_number === currentPage.value)
})

// Bookmark state
const isBookmarked = ref(false)
const bookmarkId = ref<number | null>(null)

// Check bookmark status when page changes
watch(currentPage, async () => {
  if (documentId.value && currentPage.value) {
    await checkBookmarkStatus()
  }
})

// Check bookmark status
async function checkBookmarkStatus() {
  if (!documentId.value || !currentPage.value) return
  try {
    const bookmark = await getBookmark(documentId.value, currentPage.value)
    if (bookmark) {
      isBookmarked.value = true
      bookmarkId.value = bookmark.id
    } else {
      isBookmarked.value = false
      bookmarkId.value = null
    }
  } catch {
    isBookmarked.value = false
    bookmarkId.value = null
  }
}

// Handle bookmark toggle
async function handleToggleBookmark() {
  if (!documentId.value || !currentPage.value) return
  
  try {
    if (isBookmarked.value && bookmarkId.value) {
      // Delete bookmark
      await deleteBookmark(bookmarkId.value)
      isBookmarked.value = false
      bookmarkId.value = null
      notify.success(isZh.value ? '书签已删除' : 'Bookmark removed')
    } else {
      // Create bookmark
      const data: CreateBookmarkData = {
        page_number: currentPage.value,
      }
      const result = await createBookmark(documentId.value, data)
      isBookmarked.value = true
      bookmarkId.value = result.bookmark.id
      notify.success(isZh.value ? '书签已添加' : 'Bookmark added')
    }
  } catch (error) {
    console.error('[LibraryViewerPage] Failed to toggle bookmark:', error)
    notify.error(isZh.value ? '操作失败' : 'Operation failed')
  }
}

// Fetch document on mount
onMounted(async () => {
  await libraryStore.fetchDocument(documentId.value)
  await checkBookmarkStatus()
})

// Cleanup on unmount
onUnmounted(() => {
  libraryStore.clearCurrentDocument()
})

// Watch for errors and show notifications
watch(
  () => libraryStore.currentDocumentError,
  (error) => {
    if (error) {
      const errorMessage = error.message || '加载文档失败'
      notify.error(errorMessage)
    }
  }
)

watch(
  () => libraryStore.danmakuError,
  (error) => {
    if (error) {
      const errorMessage = error.message || '加载评论失败'
      notify.error(errorMessage)
    }
  }
)

// Handle page change from PDF viewer
function handlePageChange(pageNumber: number) {
  libraryStore.fetchDanmaku(pageNumber)
  // Clear selected pin when page changes
  selectedDanmakuId.value = null
  pinPlacementPosition.value = null
}

// Handle pin placement (user clicks on page to place a pin)
function handlePinPlace(x: number, y: number, pageNumber: number) {
  pinPlacementPosition.value = { x, y, pageNumber }
  selectedDanmakuId.value = null // Clear any selected pin
  // Note: Temporary pin is shown in PdfViewer, will be cleared when comment is created
}

// Handle pin click (user clicks on existing pin to see comments)
function handlePinClick(danmakuId: number) {
  selectedDanmakuId.value = danmakuId
  pinPlacementPosition.value = null // Clear pin placement mode
}

// Toolbar event handlers
function handlePreviousPage() {
  pdfViewerRef.value?.goToPage(currentPage.value - 1)
}

function handleNextPage() {
  pdfViewerRef.value?.goToPage(currentPage.value + 1)
}

function handleGoToPage(page: number) {
  pdfViewerRef.value?.goToPage(page)
}

function handleZoomIn() {
  pdfViewerRef.value?.zoomIn()
}

function handleZoomOut() {
  pdfViewerRef.value?.zoomOut()
}

function handleFitWidth() {
  pdfViewerRef.value?.fitWidth()
}

function handleFitPage() {
  pdfViewerRef.value?.fitPage()
}

function handleRotate() {
  pdfViewerRef.value?.rotate()
}

function handlePrint() {
  pdfViewerRef.value?.print()
}

function handleSearch() {
  // TODO: Implement search functionality
  notify.info('搜索功能即将推出')
}

function handleTogglePinMode() {
  pdfViewerRef.value?.togglePinMode()
}

// Close comment panel
function handleCloseCommentPanel() {
  selectedDanmakuId.value = null
  pinPlacementPosition.value = null
  // Clear temporary pin in viewer
  if (pdfViewerRef.value) {
    pdfViewerRef.value.clearTemporaryPin()
  }
  // Disable pin mode when closing panel
  if (pdfViewerRef.value?.pinMode) {
    pdfViewerRef.value.togglePinMode()
  }
}

// Watch for pin placement position changes to clear temporary pin when comment is created
watch(pinPlacementPosition, (newVal) => {
  // When pinPlacementPosition is cleared (after comment creation), clear temporary pin
  if (!newVal && pdfViewerRef.value) {
    pdfViewerRef.value.clearTemporaryPin()
  }
})
</script>

<template>
  <div class="library-viewer-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="library-viewer-header px-4 h-14 bg-white border-b border-stone-200 flex items-center justify-between">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <ElButton
          text
          circle
          size="small"
          class="shrink-0 back-button"
          @click="router.push('/library')"
        >
          <ArrowLeft class="w-4 h-4" />
        </ElButton>
        <h1 class="text-sm font-semibold text-stone-900 truncate">
          {{ libraryStore.currentDocument?.title || '加载中...' }}
        </h1>
      </div>
    </div>

    <!-- PDF Toolbar -->
    <PdfToolbar
      v-if="libraryStore.currentDocument && totalPages > 0"
      :current-page="currentPage"
      :total-pages="totalPages"
      :zoom="zoom"
      :can-go-previous="canGoPrevious"
      :can-go-next="canGoNext"
      :pin-mode="pinMode"
      :is-bookmarked="isBookmarked"
      @previous-page="handlePreviousPage"
      @next-page="handleNextPage"
      @go-to-page="handleGoToPage"
      @zoom-in="handleZoomIn"
      @zoom-out="handleZoomOut"
      @fit-width="handleFitWidth"
      @fit-page="handleFitPage"
      @rotate="handleRotate"
      @print="handlePrint"
      @search="handleSearch"
      @toggle-pin-mode="handleTogglePinMode"
      @toggle-bookmark="handleToggleBookmark"
    />

    <!-- Main content area -->
    <div class="library-viewer-content flex-1 flex overflow-hidden">
      <!-- PDF Viewer with Danmaku Overlay -->
      <div class="flex-1 relative overflow-hidden pb-4">
        <PdfViewer
          ref="pdfViewerRef"
          v-if="libraryStore.currentDocument && pdfUrl"
          :pdf-url="pdfUrl"
          :document-id="documentId"
          :danmaku="currentPageDanmaku"
          @page-change="handlePageChange"
          @pin-place="handlePinPlace"
          @pin-click="handlePinClick"
        />
        <DanmakuOverlay
          v-if="libraryStore.currentDocument"
          :document-id="documentId"
          :current-page="libraryStore.currentPage"
        />
      </div>

      <!-- Comment Panel - Show when pin is placed or clicked -->
      <CommentPanel
        v-if="libraryStore.currentDocument && (pinPlacementPosition || selectedDanmakuId)"
        :document-id="documentId"
        :current-page="currentPage"
        :pin-position="pinPlacementPosition"
        :danmaku-id="selectedDanmakuId"
        @close="handleCloseCommentPanel"
      />
    </div>
  </div>
</template>

<style scoped>
.library-viewer-page {
  min-height: 0;
}

/* Back button - Match MindMate style */
.back-button {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
