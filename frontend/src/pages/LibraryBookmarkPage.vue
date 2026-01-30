<script setup lang="ts">
/**
 * LibraryBookmarkPage - Navigate to bookmark by UUID
 * If bookmark doesn't exist or doesn't belong to user, show 404
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getBookmarkByUuid } from '@/utils/apiClient'
import { useNotifications } from '@/composables'

const route = useRoute()
const router = useRouter()
const notify = useNotifications()

const bookmarkUuid = route.params.uuid as string

onMounted(async () => {
  try {
    const bookmark = await getBookmarkByUuid(bookmarkUuid)
    // Navigate to the document viewer at the bookmarked page
    router.replace({
      name: 'LibraryViewer',
      params: { id: bookmark.document_id.toString() },
      query: { page: bookmark.page_number.toString() },
    })
  } catch (error) {
    // Bookmark not found or doesn't belong to user - show 404
    console.error('[LibraryBookmarkPage] Bookmark not found:', error)
    router.replace({ name: 'NotFound' })
  }
})
</script>

<template>
  <div class="flex items-center justify-center h-screen">
    <div class="text-center">
      <p>正在加载书签...</p>
    </div>
  </div>
</template>
