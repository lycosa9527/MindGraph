<script setup lang="ts">
/**
 * CommentPanel - Side panel for managing danmaku comments
 * Supports text selection mode and position mode
 */
import { ref, computed, watch } from 'vue'
import { Heart, MessageSquare, Send, Loader2, X } from 'lucide-vue-next'

import { useLibraryStore } from '@/stores/library'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables'
import type { CreateDanmakuData, CreateReplyData } from '@/utils/apiClient'

interface Props {
  documentId: number
  currentPage: number | null
  selectedText: string | null
  selectedTextBbox: { x: number; y: number; width: number; height: number } | null
}

const props = defineProps<Props>()

const libraryStore = useLibraryStore()
const authStore = useAuthStore()
const notify = useNotifications()

// Show panel only when text is selected
const showPanel = computed(() => !!props.selectedText)
const newComment = ref('')
const replyingTo = ref<number | null>(null)
const replyContent = ref('')
const creatingComment = ref(false)
const creatingReply = ref<Record<number, boolean>>({})

// Get danmaku for current context
const displayedDanmaku = computed(() => {
  if (props.selectedText) {
    return libraryStore.danmakuForText(props.selectedText)
  }
  if (props.currentPage) {
    return libraryStore.danmakuForPage(props.currentPage)
  }
  return []
})

// Watch for page/text changes
watch(
  () => [props.currentPage, props.selectedText],
  async ([page, text]) => {
    if (page) {
      await libraryStore.fetchDanmaku(page, text || undefined)
    }
  },
  { immediate: true }
)

// Create danmaku comment
async function createComment() {
  if (!newComment.value.trim() || !props.currentPage || creatingComment.value) return

  const data: CreateDanmakuData = {
    content: newComment.value.trim(),
    page_number: props.currentPage,
  }

  if (props.selectedText) {
    data.selected_text = props.selectedText
    if (props.selectedTextBbox) {
      data.text_bbox = props.selectedTextBbox
    }
  }

  creatingComment.value = true
  try {
    await libraryStore.createDanmakuComment(data)
    newComment.value = ''
    notify.success('评论已添加')
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '创建评论失败'
    notify.error(errorMessage)
    console.error('[CommentPanel] Failed to create comment:', error)
  } finally {
    creatingComment.value = false
  }
}

// Toggle like
async function toggleLike(danmakuId: number) {
  try {
    await libraryStore.toggleDanmakuLike(danmakuId)
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '操作失败'
    notify.error(errorMessage)
    console.error('[CommentPanel] Failed to toggle like:', error)
  }
}

// Start replying
function startReply(danmakuId: number) {
  replyingTo.value = danmakuId
  libraryStore.fetchReplies(danmakuId)
}

// Submit reply
async function submitReply(danmakuId: number) {
  if (!replyContent.value.trim() || creatingReply.value[danmakuId]) return

  const data: CreateReplyData = {
    content: replyContent.value.trim(),
  }

  creatingReply.value[danmakuId] = true
  try {
    await libraryStore.createReply(danmakuId, data)
    replyContent.value = ''
    replyingTo.value = null
    notify.success('回复已添加')
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '创建回复失败'
    notify.error(errorMessage)
    console.error('[CommentPanel] Failed to create reply:', error)
  } finally {
    creatingReply.value[danmakuId] = false
  }
}

// Cancel reply
function cancelReply() {
  replyContent.value = ''
  replyingTo.value = null
}

// Clear text selection (close panel)
function clearSelection() {
  libraryStore.selectedText = null
  libraryStore.selectedTextBbox = null
}
</script>

<template>
  <div
    v-if="showPanel"
    class="comment-panel w-80 bg-white border-l border-stone-200 flex flex-col"
  >
    <!-- Header -->
    <div class="px-4 py-3 border-b border-stone-200 flex items-start justify-between gap-2">
      <div class="flex-1 min-w-0">
        <h3 class="text-sm font-semibold text-stone-900">
          {{ selectedText ? '评论' : `第 ${currentPage} 页评论` }}
        </h3>
        <p
          v-if="selectedText"
          class="text-xs text-stone-500 mt-1 line-clamp-2"
        >
          "{{ selectedText }}"
        </p>
      </div>
      <button
        v-if="selectedText"
        class="flex-shrink-0 p-1 text-stone-400 hover:text-stone-600 transition-colors"
        @click="clearSelection"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Comments List -->
    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div
        v-if="libraryStore.danmakuLoading"
        class="flex items-center justify-center py-8"
      >
        <Loader2 class="w-6 h-6 animate-spin text-stone-400" />
      </div>
      <div
        v-for="danmaku in displayedDanmaku"
        :key="danmaku.id"
        class="comment-item"
      >
        <!-- Comment Content -->
        <div class="flex items-start gap-3">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-medium text-stone-700">
                {{ danmaku.user.name || '匿名' }}
              </span>
            </div>
            <p class="text-sm text-stone-800 mb-2">{{ danmaku.content }}</p>
            <div class="flex items-center gap-4">
              <button
                class="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700"
                :class="{ 'text-red-500': danmaku.is_liked }"
                @click="toggleLike(danmaku.id)"
              >
                <Heart
                  :class="['w-4 h-4', danmaku.is_liked ? 'fill-current' : '']"
                />
                <span>{{ danmaku.likes_count }}</span>
              </button>
              <button
                class="flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700"
                @click="startReply(danmaku.id)"
              >
                <MessageSquare class="w-4 h-4" />
                <span>回复</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Replies -->
        <div
          v-if="replyingTo === danmaku.id && libraryStore.replies[danmaku.id]"
          class="ml-6 mt-2 space-y-2"
        >
          <div
            v-for="reply in libraryStore.replies[danmaku.id]"
            :key="reply.id"
            class="text-xs text-stone-600"
          >
            <span class="font-medium">{{ reply.user.name || '匿名' }}:</span>
            <span class="ml-1">{{ reply.content }}</span>
          </div>
        </div>

        <!-- Reply Input -->
        <div
          v-if="replyingTo === danmaku.id"
          class="ml-6 mt-2 flex gap-2"
        >
          <input
            v-model="replyContent"
            type="text"
            placeholder="输入回复..."
            class="flex-1 px-2 py-1 text-xs border border-stone-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500"
            @keyup.enter="submitReply(danmaku.id)"
          />
          <button
            class="px-2 py-1 text-xs bg-indigo-500 text-white rounded hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
            :disabled="creatingReply[danmaku.id]"
            @click="submitReply(danmaku.id)"
          >
            <Loader2
              v-if="creatingReply[danmaku.id]"
              class="w-3 h-3 animate-spin"
            />
            <span>发送</span>
          </button>
          <button
            class="px-2 py-1 text-xs text-stone-500 hover:text-stone-700"
            @click="cancelReply"
          >
            取消
          </button>
        </div>
      </div>

      <div
        v-if="!libraryStore.danmakuLoading && displayedDanmaku.length === 0"
        class="text-center text-stone-400 text-sm py-8"
      >
        暂无评论
      </div>
    </div>

    <!-- Comment Input -->
    <div
      v-if="authStore.isAuthenticated && currentPage"
      class="border-t border-stone-200 p-4"
    >
      <div class="flex gap-2">
        <input
          v-model="newComment"
          type="text"
          placeholder="添加评论..."
          class="flex-1 px-3 py-2 text-sm border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          @keyup.enter="createComment"
        />
        <button
          class="px-4 py-2 bg-stone-900 text-white rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          :disabled="creatingComment"
          @click="createComment"
        >
          <Loader2
            v-if="creatingComment"
            class="w-4 h-4 animate-spin"
          />
          <Send
            v-else
            class="w-4 h-4"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.comment-panel {
  min-height: 0;
}

.comment-item {
  padding-bottom: 1rem;
  border-bottom: 1px solid #e7e5e4;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-panel::-webkit-scrollbar {
  width: 6px;
}

.comment-panel::-webkit-scrollbar-track {
  background: transparent;
}

.comment-panel::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.comment-panel::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}
</style>
