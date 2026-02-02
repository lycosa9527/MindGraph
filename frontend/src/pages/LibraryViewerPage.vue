<script setup lang="ts">
/**
 * LibraryViewerPage - Image viewer with danmaku and comments
 * Combines ImageViewer, DanmakuOverlay, and CommentPanel components
 */
import { onMounted, onUnmounted, computed, watch, ref, nextTick } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'

import { ElButton, ElIcon } from 'element-plus'
import { ArrowLeft } from 'lucide-vue-next'

import { LoginModal } from '@/components/auth'
import { useLibraryStore } from '@/stores/library'
import { useAuthStore } from '@/stores/auth'
import { useNotifications, useLanguage } from '@/composables'

import ImageViewer from '@/components/library/ImageViewer.vue'
import PdfToolbar from '@/components/library/PdfToolbar.vue'
import DanmakuOverlay from '@/components/library/DanmakuOverlay.vue'
import CommentPanel from '@/components/library/CommentPanel.vue'

const route = useRoute()
const router = useRouter()
const libraryStore = useLibraryStore()
const authStore = useAuthStore()
const notify = useNotifications()
const { isZh } = useLanguage()

const showLoginModal = ref(false)
const imageViewerRef = ref<InstanceType<typeof ImageViewer> | null>(null)

const documentId = computed(() => parseInt(route.params.id as string))

// Get initial page from query parameter
const initialPageFromQuery = computed(() => {
  const pageParam = route.query.page
  if (pageParam) {
    const pageNum = parseInt(pageParam as string, 10)
    if (!isNaN(pageNum) && pageNum >= 1) {
      return pageNum
    }
  }
  return 1
})

// Check if document uses images (should always be true now)
const useImages = computed(() => libraryStore.currentDocument?.use_images ?? false)
const totalPagesFromDoc = computed(() => libraryStore.currentDocument?.total_pages ?? 0)

// Get viewer ref (ImageViewer only)
const viewerRef = computed(() => imageViewerRef.value)

const currentPage = computed(() => viewerRef.value?.currentPage || 1)
const totalPages = computed(() => totalPagesFromDoc.value || 0)
const zoom = computed(() => viewerRef.value?.zoom || 1.0)
const pinMode = computed(() => viewerRef.value?.pinMode ?? false)
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

// Check bookmark status when page changes (only if authenticated)
watch(currentPage, async () => {
  if (authStore.isAuthenticated && documentId.value && currentPage.value) {
    await checkBookmarkStatus()
  }
})

// Check bookmark status
async function checkBookmarkStatus() {
  if (!authStore.isAuthenticated || !documentId.value || !currentPage.value) return
  
  // Don't check bookmarks for pages we know don't exist
  if (false) {
    // Page doesn't exist - don't check for bookmark
    isBookmarked.value = false
    bookmarkId.value = null
    return
  }
  
  try {
    const bookmark = await libraryStore.getBookmark(documentId.value, currentPage.value)
    if (bookmark) {
      isBookmarked.value = true
      bookmarkId.value = bookmark.id
    } else {
      isBookmarked.value = false
      bookmarkId.value = null
    }
  } catch (error) {
    // 404 means bookmark doesn't exist - this is expected and fine
    // Don't log as error since this is normal behavior
    if (error instanceof Error && (error.message.includes('404') || error.message.includes('Failed to fetch'))) {
      // Bookmark doesn't exist - expected, silently handle
      isBookmarked.value = false
      bookmarkId.value = null
    } else {
      // Other errors - log at debug level but don't show error to user
      console.debug('[LibraryViewerPage] Bookmark check failed (non-404):', error)
      isBookmarked.value = false
      bookmarkId.value = null
    }
  }
}

// Handle bookmark toggle
async function handleToggleBookmark() {
  if (!authStore.isAuthenticated) {
    openLoginModal()
    return
  }

  console.log('[LibraryViewerPage] handleToggleBookmark called', {
    documentId: documentId.value,
    currentPage: currentPage.value,
    isBookmarked: isBookmarked.value,
    bookmarkId: bookmarkId.value,
  })

  if (!documentId.value || !currentPage.value) {
    console.warn('[LibraryViewerPage] Cannot toggle bookmark: missing documentId or currentPage')
    return
  }

  try {
    if (isBookmarked.value && bookmarkId.value) {
      // Delete bookmark
      console.log('[LibraryViewerPage] Deleting bookmark:', bookmarkId.value)
      await libraryStore.deleteBookmark(bookmarkId.value)
      isBookmarked.value = false
      bookmarkId.value = null
      notify.success(isZh.value ? '书签已删除' : 'Bookmark removed')
    } else {
      // Create bookmark
      const data = {
        page_number: currentPage.value,
      }
      console.log('[LibraryViewerPage] Creating bookmark:', data)
      const bookmark = await libraryStore.createBookmark(documentId.value, data)
      console.log('[LibraryViewerPage] Bookmark created:', bookmark)
      isBookmarked.value = true
      bookmarkId.value = bookmark.id
      notify.success(isZh.value ? '书签已添加' : 'Bookmark added')
    }
  } catch (error) {
    console.error('[LibraryViewerPage] Failed to toggle bookmark:', error)
    if (error instanceof Error) {
      notify.error(error.message || (isZh.value ? '操作失败' : 'Operation failed'))
    } else {
      notify.error(isZh.value ? '操作失败' : 'Operation failed')
    }
  }
}

// Track if we've already navigated to avoid duplicate navigation
const hasNavigatedToPage = ref(false)

// Navigate to page from query parameter
async function navigateToPageFromQuery() {
  const pageParam = route.query.page
  if (!pageParam) {
    hasNavigatedToPage.value = false
    return
  }

  const pageNum = parseInt(pageParam as string, 10)
  if (isNaN(pageNum) || pageNum < 1) return

  // Wait for document to be loaded and totalPages to be available
  if (!libraryStore.currentDocument || totalPages.value === 0) {
    console.log('[LibraryViewerPage] Waiting for document to load...')
    return
  }

  // Check if page is valid
  if (pageNum > totalPages.value) {
    console.warn(`[LibraryViewerPage] Page ${pageNum} exceeds total pages ${totalPages.value}`)
    return
  }

  // Wait for viewer to be ready
  await nextTick()
  let retries = 0
  while (!viewerRef.value && retries < 30) {
    await new Promise((resolve) => setTimeout(resolve, 100))
    retries++
  }

  if (!viewerRef.value) {
    console.error('[LibraryViewerPage] Viewer not ready after waiting')
    return
  }

  // Check if we're already on the correct page
  if (currentPage.value === pageNum) {
    console.log(`[LibraryViewerPage] Already on page ${pageNum}`)
    return
  }

  // If we've already navigated and we're on the wrong page, don't navigate again
  // (this prevents multiple navigation calls from different watchers)
  if (hasNavigatedToPage.value && currentPage.value !== pageNum) {
    console.log(`[LibraryViewerPage] Navigation already attempted, waiting...`)
    return
  }

  // Wait a bit more for ImageViewer to finish initializing
  await new Promise((resolve) => setTimeout(resolve, 200))

  // Navigate to the specified page
  console.log(`[LibraryViewerPage] Navigating to page ${pageNum} from query parameter`)
  hasNavigatedToPage.value = true
  viewerRef.value.goToPage(pageNum)
  
  // Check bookmark status after navigating
  await nextTick()
  await checkBookmarkStatus()
}

// Fetch document on mount (only if authenticated)
onMounted(async () => {
  if (!authStore.isAuthenticated) {
    return
  }

  try {
    await libraryStore.fetchDocument(documentId.value)

    // Check if document was loaded successfully
    if (!libraryStore.currentDocument) {
      console.error('[LibraryViewerPage] Document not found:', documentId.value)
      router.replace({ name: 'NotFound' })
      return
    }

    // Wait for viewer to mount and initialize with initialPage prop
    // The ImageViewer will use the initialPage prop to load the correct page
    // We don't need to call navigateToPageFromQuery here since initialPage prop handles it
    // But we'll check bookmark status after a short delay
    if (route.query.page) {
      // Wait for viewer to initialize with initialPage prop
      await nextTick()
      setTimeout(async () => {
        // Verify we're on the correct page, navigate if needed
        await navigateToPageFromQuery()
        await checkBookmarkStatus()
      }, 600)
    } else {
      // No page param - check bookmark status for current page
      await checkBookmarkStatus()
    }
  } catch (error) {
    console.error('[LibraryViewerPage] Failed to load document:', error)
    // Check if document error indicates 404
    if (libraryStore.currentDocumentError) {
      const errorMsg = libraryStore.currentDocumentError.message.toLowerCase()
      if (errorMsg.includes('404') || errorMsg.includes('not found')) {
        router.replace({ name: 'NotFound' })
        return
      }
    }
    // If document doesn't exist, navigate to 404
    if (error instanceof Error && (error.message.includes('404') || error.message.includes('not found'))) {
      router.replace({ name: 'NotFound' })
    }
  }
})

// Watch for authentication changes and fetch document when user logs in
watch(
  () => authStore.isAuthenticated,
  async (isAuthenticated) => {
    if (isAuthenticated && !libraryStore.currentDocument) {
      try {
        await libraryStore.fetchDocument(documentId.value)
        if (route.query.page) {
          await nextTick()
          setTimeout(async () => {
            await navigateToPageFromQuery()
            await checkBookmarkStatus()
          }, 600)
        } else {
          await checkBookmarkStatus()
        }
      } catch (error) {
        console.error('[LibraryViewerPage] Failed to load document after login:', error)
      }
    }
  }
)

// Watch for route query changes (e.g., when clicking bookmark)
watch(
  () => route.query.page,
  async (newPage, oldPage) => {
    // Reset navigation flag when page query changes
    if (newPage !== oldPage) {
      hasNavigatedToPage.value = false
    }
    if (newPage && libraryStore.currentDocument && viewerRef.value) {
      await navigateToPageFromQuery()
    }
  }
)

// Watch for document changes to handle navigation when document loads
watch(
  () => libraryStore.currentDocument,
  async (newDoc) => {
    if (newDoc && route.query.page && viewerRef.value && !hasNavigatedToPage.value) {
      // Wait for viewer to initialize with initialPage prop
      await nextTick()
      setTimeout(async () => {
        await navigateToPageFromQuery()
      }, 500)
    }
  }
)

// Watch for viewer to become available and navigate if needed
watch(
  () => viewerRef.value,
  async (newViewer) => {
    if (newViewer && route.query.page && libraryStore.currentDocument && !hasNavigatedToPage.value) {
      // Wait a bit for ImageViewer to finish initializing with initialPage prop
      setTimeout(async () => {
        await navigateToPageFromQuery()
      }, 300)
    }
  }
)

// Cleanup on unmount
onUnmounted(() => {
  libraryStore.clearCurrentDocument()
})

// Watch for errors and show notifications or navigate to 404
watch(
  () => libraryStore.currentDocumentError,
  (error) => {
    if (error) {
      const errorMessage = error.message || '加载文档失败'
      // Check if it's a 404 error
      if (errorMessage.includes('404') || errorMessage.includes('not found')) {
        router.replace({ name: 'NotFound' })
      } else {
        notify.error(errorMessage)
      }
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

// Handle page change from image viewer
function handlePageChange(pageNumber: number) {
  if (authStore.isAuthenticated) {
    libraryStore.fetchDanmaku(pageNumber)
  }
  // Clear selected pin when page changes
  selectedDanmakuId.value = null
  pinPlacementPosition.value = null
}

// Open login modal
function openLoginModal() {
  showLoginModal.value = true
}

// Handle successful login
function handleLoginSuccess() {
  showLoginModal.value = false
  // Fetch document after login
  if (authStore.isAuthenticated && documentId.value) {
    libraryStore.fetchDocument(documentId.value).then(() => {
      if (route.query.page) {
        nextTick().then(() => {
          setTimeout(async () => {
            await navigateToPageFromQuery()
            await checkBookmarkStatus()
          }, 600)
        })
      } else {
        checkBookmarkStatus()
      }
    })
  }
}

// Handle pin placement (user clicks on page to place a pin)
function handlePinPlace(x: number, y: number, pageNumber: number) {
  pinPlacementPosition.value = { x, y, pageNumber }
  selectedDanmakuId.value = null // Clear any selected pin
  // Note: Temporary pin is shown in ImageViewer, will be cleared when comment is created
}

// Handle pin click (user clicks on existing pin to see comments)
function handlePinClick(danmakuId: number) {
  selectedDanmakuId.value = danmakuId
  pinPlacementPosition.value = null // Clear pin placement mode
}

// Toolbar event handlers
function handlePreviousPage() {
  viewerRef.value?.goToPreviousPage()
}

function handleNextPage() {
  viewerRef.value?.goToNextPage()
}

function handleGoToPage(page: number) {
  viewerRef.value?.goToPage(page)
}

function handleZoomIn() {
  viewerRef.value?.zoomIn()
}

function handleZoomOut() {
  viewerRef.value?.zoomOut()
}

function handleZoomChange(zoomValue: number) {
  viewerRef.value?.setZoom(zoomValue)
}

function handleRotate() {
  viewerRef.value?.rotate()
}

function handlePrint() {
  viewerRef.value?.print()
}

function handleTogglePinMode() {
  viewerRef.value?.togglePinMode()
}

// Close comment panel
function handleCloseCommentPanel() {
  selectedDanmakuId.value = null
  pinPlacementPosition.value = null
  // Clear temporary pin in viewer
  if (viewerRef.value) {
    viewerRef.value.clearTemporaryPin()
  }
  // Disable pin mode when closing panel
  if (viewerRef.value?.pinMode) {
    viewerRef.value.togglePinMode()
  }
}

// Watch for pin placement position changes to clear temporary pin when comment is created
watch(pinPlacementPosition, (newVal) => {
  // When pinPlacementPosition is cleared (after comment creation), clear temporary pin
  if (!newVal && viewerRef.value) {
    viewerRef.value.clearTemporaryPin()
  }
})

// Watch for comment panel open/close to re-render pins when layout changes
watch(
  [() => selectedDanmakuId.value, () => pinPlacementPosition.value],
  () => {
    // When comment panel opens or closes, the layout changes and image resizes
    // Wait for layout to settle, then re-render pins
    nextTick(() => {
      setTimeout(() => {
        if (viewerRef.value && imageViewerRef.value) {
          // Trigger re-render by calling renderPins through the component
          // We'll expose a method or trigger it via a watcher
          const viewer = imageViewerRef.value as any
          if (viewer.renderPins) {
            viewer.renderPins()
          }
        }
      }, 150)
    })
  }
)
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
      @zoom-change="handleZoomChange"
      @rotate="handleRotate"
      @print="handlePrint"
      @toggle-pin-mode="handleTogglePinMode"
      @toggle-bookmark="handleToggleBookmark"
    />

    <!-- Main content area -->
    <div
      class="library-viewer-content flex-1 flex overflow-hidden relative"
      :class="{ 'blurred': !authStore.isAuthenticated }"
    >
      <!-- Viewer with Danmaku Overlay -->
      <div class="flex-1 relative overflow-hidden" style="padding-bottom: 30px;">
        <!-- Image Viewer -->
        <ImageViewer
          v-if="libraryStore.currentDocument && totalPages > 0"
          ref="imageViewerRef"
          :document-id="documentId"
          :total-pages="totalPages"
          :danmaku="currentPageDanmaku"
          :initial-page="initialPageFromQuery"
          @pageChange="handlePageChange"
          @pinPlace="handlePinPlace"
          @pinClick="handlePinClick"
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

    <!-- Login Modal -->
    <LoginModal
      v-model:visible="showLoginModal"
      @success="handleLoginSuccess"
    />
  </div>
</template>

<style scoped>
.library-viewer-page {
  min-height: 0;
  position: relative;
}

.library-viewer-content.blurred {
  filter: blur(8px);
  pointer-events: none;
  user-select: none;
}

/* Back button - Match MindMate style */
.back-button {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
}
</style>
