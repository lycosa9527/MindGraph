<script setup lang="ts">
/**
 * LibraryPage - Simple Swiss design with 4 cover images in grid
 * Clean, minimal design with book names underneath covers
 * Organized into groups: 精品案例集 and 其他
 */
import { onMounted, watch, ref, computed } from 'vue'
import { useRouter } from 'vue-router'

import { BookOpen } from 'lucide-vue-next'

import { LoginModal } from '@/components/auth'
import { useNotifications } from '@/composables'
import { useLibraryStore } from '@/stores/library'
import { useAuthStore } from '@/stores/auth'
import { getLibraryDocumentCoverUrl } from '@/utils/apiClient'
import type { LibraryDocument } from '@/utils/apiClient'

const router = useRouter()
const libraryStore = useLibraryStore()
const authStore = useAuthStore()
const notify = useNotifications()

const showLoginModal = ref(false)

// Track which cover images have loaded successfully
const coverImageLoaded = ref<Record<number, boolean>>({})

// Hardcoded book titles for 精品案例集 group
// These 4 books will be uploaded to the server
const PREMIUM_BOOK_TITLES = [
  '思维发展型课堂的理论与实践第一辑',
  '思维发展型课堂的理论与实践第二辑',
  '思维发展型课堂的理论与实践第三辑',
  '思维发展型课堂的理论与实践第四辑',
]

// Group books into categories
const premiumBooks = computed(() => {
  return libraryStore.documents.filter((doc) => {
    return PREMIUM_BOOK_TITLES.includes(doc.title)
  })
})

const otherBooks = computed(() => {
  return libraryStore.documents.filter((doc) => {
    return !PREMIUM_BOOK_TITLES.includes(doc.title)
  })
})

// Fetch documents on mount (always fetch, even if not authenticated)
onMounted(async () => {
  try {
    await libraryStore.fetchDocuments(1, 20)
  } catch (error) {
    // Silently handle auth errors - user will see blurred empty state
    // Don't show error notification for unauthenticated users
    if (authStore.isAuthenticated) {
      const errorMessage = error instanceof Error ? error.message : '加载文档列表失败'
      notify.error(errorMessage)
    }
  }
})

// Watch for errors and show notifications (only if authenticated)
watch(
  () => libraryStore.documentsError,
  (error) => {
    if (error && authStore.isAuthenticated) {
      const errorMessage = error.message || '加载文档列表失败'
      notify.error(errorMessage)
    }
  }
)

// Watch for authentication changes and refresh documents when user logs in
watch(
  () => authStore.isAuthenticated,
  async (isAuthenticated) => {
    if (isAuthenticated) {
      // Refresh documents after login
      try {
        await libraryStore.fetchDocuments(1, 20)
      } catch (error) {
        // Handle error silently or show notification
        const errorMessage = error instanceof Error ? error.message : '加载文档列表失败'
        notify.error(errorMessage)
      }
    }
  }
)

// Get cover image URL
function getCoverUrl(documentId: number): string {
  return getLibraryDocumentCoverUrl(documentId)
}

// Handle cover image load error (404 or other error)
function handleCoverError(event: Event) {
  const img = event.target as HTMLImageElement
  const src = img.src
  // Extract document ID from URL: /api/library/documents/{id}/cover
  const match = src.match(/\/documents\/(\d+)\/cover/)
  if (match) {
    const documentId = parseInt(match[1], 10)
    coverImageLoaded.value[documentId] = false
  }
}

// Handle cover image load success
function handleCoverLoad(event: Event) {
  const img = event.target as HTMLImageElement
  const src = img.src
  const match = src.match(/\/documents\/(\d+)\/cover/)
  if (match) {
    const documentId = parseInt(match[1], 10)
    coverImageLoaded.value[documentId] = true
  }
}

// Navigate to PDF viewer
function openDocument(documentId: number) {
  if (!authStore.isAuthenticated) {
    // Don't open modal, just prevent navigation
    return
  }
  router.push(`/library/${documentId}`)
}

// Open login modal
function openLoginModal() {
  showLoginModal.value = true
}

// Handle successful login
function handleLoginSuccess() {
  showLoginModal.value = false
  // Fetch documents after login
  if (authStore.isAuthenticated) {
    libraryStore.fetchDocuments(1, 20)
  }
}
</script>

<template>
  <div class="library-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header -->
    <div class="library-header h-14 px-4 flex items-center bg-white border-b border-stone-200">
      <h1 class="text-sm font-semibold text-stone-900">图书馆</h1>
    </div>

    <!-- Content -->
    <div
      class="library-content flex-1 overflow-y-auto px-6 pt-4 pb-6"
      :class="{ 'blurred': !authStore.isAuthenticated }"
    >
      <div
        v-if="libraryStore.documentsLoading"
        class="flex items-center justify-center h-full"
      >
        <div class="text-stone-400">加载中...</div>
      </div>

      <div
        v-else-if="libraryStore.documentsError"
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <BookOpen class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">加载失败</p>
        <p class="text-sm">{{ libraryStore.documentsError.message }}</p>
      </div>

      <!-- Books organized by groups -->
      <div
        v-else-if="libraryStore.documents.length > 0"
        class="max-w-4xl mx-auto space-y-6"
      >
        <!-- 精品案例集 Group -->
        <div v-if="premiumBooks.length > 0">
          <h2 class="text-lg font-semibold text-stone-900 mb-3">精品案例集</h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div
              v-for="document in premiumBooks"
              :key="document.id"
              class="book-card cursor-pointer group"
              @click="openDocument(document.id)"
            >
              <!-- Cover Image -->
              <div
                class="aspect-3/4 rounded-lg overflow-hidden mb-3 bg-stone-200 relative border border-stone-300"
              >
                <img
                  :src="getCoverUrl(document.id)"
                  :alt="document.title"
                  class="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                  @error="handleCoverError"
                  @load="handleCoverLoad"
                />
                <div
                  v-show="!coverImageLoaded[document.id]"
                  class="w-full h-full flex items-center justify-center bg-linear-to-br from-stone-200 to-stone-300 absolute inset-0"
                >
                  <BookOpen class="w-12 h-12 text-stone-400" />
                </div>
              </div>

              <!-- Book Title -->
              <h3
                class="text-sm font-medium text-stone-800 text-center line-clamp-2 group-hover:text-indigo-600 transition-colors"
              >
                {{ document.title }}
              </h3>
            </div>
          </div>
        </div>

        <!-- 其他 Group -->
        <div v-if="otherBooks.length > 0">
          <h2 class="text-lg font-semibold text-stone-900 mb-3">其他</h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div
              v-for="document in otherBooks"
              :key="document.id"
              class="book-card cursor-pointer group"
              @click="openDocument(document.id)"
            >
              <!-- Cover Image -->
              <div
                class="aspect-3/4 rounded-lg overflow-hidden mb-3 bg-stone-200 relative border border-stone-300"
              >
                <img
                  :src="getCoverUrl(document.id)"
                  :alt="document.title"
                  class="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                  @error="handleCoverError"
                  @load="handleCoverLoad"
                />
                <div
                  v-show="!coverImageLoaded[document.id]"
                  class="w-full h-full flex items-center justify-center bg-linear-to-br from-stone-200 to-stone-300 absolute inset-0"
                >
                  <BookOpen class="w-12 h-12 text-stone-400" />
                </div>
              </div>

              <!-- Book Title -->
              <h3
                class="text-sm font-medium text-stone-800 text-center line-clamp-2 group-hover:text-indigo-600 transition-colors"
              >
                {{ document.title }}
              </h3>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div
        v-else
        class="flex flex-col items-center justify-center h-full text-stone-400"
      >
        <BookOpen class="w-16 h-16 mb-4 opacity-30" />
        <p class="text-lg font-medium mb-1">暂无图书</p>
        <p class="text-sm">图书馆中还没有PDF文档</p>
      </div>
    </div>

    <!-- Login Modal -->
    <LoginModal
      v-model:visible="showLoginModal"
      @success="handleLoginSuccess"
    />
  </div>
</template>

<style scoped>
.library-page {
  min-height: 0;
  position: relative;
}

.library-content.blurred {
  pointer-events: none;
  user-select: none;
}

.book-card {
  transition: transform 0.2s ease;
}

.book-card:hover {
  transform: translateY(-2px);
}

/* Custom scrollbar */
.library-content::-webkit-scrollbar {
  width: 6px;
}

.library-content::-webkit-scrollbar-track {
  background: transparent;
}

.library-content::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.library-content::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}

/* Line clamp */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
