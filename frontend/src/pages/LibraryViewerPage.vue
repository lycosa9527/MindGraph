<script setup lang="ts">
/**
 * LibraryViewerPage - PDF viewer with danmaku and comments
 * Combines PdfViewer, DanmakuOverlay, and CommentPanel components
 */
import { onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElButton, ElIcon } from 'element-plus'
import { ArrowLeft } from 'lucide-vue-next'

import { useLibraryStore } from '@/stores/library'
import { useNotifications } from '@/composables'
import { getLibraryDocumentFileUrl } from '@/utils/apiClient'

import PdfViewer from '@/components/library/PdfViewer.vue'
import DanmakuOverlay from '@/components/library/DanmakuOverlay.vue'
import CommentPanel from '@/components/library/CommentPanel.vue'

const route = useRoute()
const router = useRouter()
const libraryStore = useLibraryStore()
const notify = useNotifications()

const documentId = computed(() => parseInt(route.params.id as string))
const pdfUrl = computed(() => {
  if (!libraryStore.currentDocument) return ''
  return getLibraryDocumentFileUrl(libraryStore.currentDocument.id)
})

// Fetch document on mount
onMounted(async () => {
  await libraryStore.fetchDocument(documentId.value)
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
}

// Handle text selection
function handleTextSelection(text: string, bbox: { x: number; y: number; width: number; height: number }, pageNumber: number) {
  libraryStore.selectedText = text
  libraryStore.selectedTextBbox = bbox
  libraryStore.fetchDanmaku(pageNumber, text)
}
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
          class="flex-shrink-0 back-button"
          @click="router.push('/library')"
        >
          <ArrowLeft class="w-4 h-4" />
        </ElButton>
        <h1 class="text-sm font-semibold text-stone-900 truncate">
          {{ libraryStore.currentDocument?.title || '加载中...' }}
        </h1>
      </div>
    </div>

    <!-- Main content area -->
    <div class="library-viewer-content flex-1 flex overflow-hidden">
      <!-- PDF Viewer with Danmaku Overlay -->
      <div class="flex-1 relative overflow-hidden">
        <PdfViewer
          v-if="libraryStore.currentDocument && pdfUrl"
          :pdf-url="pdfUrl"
          :document-id="documentId"
          @page-change="handlePageChange"
          @text-selection="handleTextSelection"
        />
        <DanmakuOverlay
          v-if="libraryStore.currentDocument"
          :document-id="documentId"
          :current-page="libraryStore.currentPage"
        />
      </div>

      <!-- Comment Panel - Only show when text is selected -->
      <CommentPanel
        v-if="libraryStore.currentDocument && libraryStore.selectedText"
        :document-id="documentId"
        :current-page="libraryStore.currentPage"
        :selected-text="libraryStore.selectedText"
        :selected-text-bbox="libraryStore.selectedTextBbox"
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
