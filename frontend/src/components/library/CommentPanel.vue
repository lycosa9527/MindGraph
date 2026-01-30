<script setup lang="ts">
/**
 * CommentPanel - Side panel for managing danmaku comments
 * Pin-based comment system
 */
import { ref, computed, watch } from 'vue'
import { Heart, MessageSquare, Send, Loader2, X, Trash2 } from 'lucide-vue-next'
import { ElButton, ElInput } from 'element-plus'

import { useLibraryStore } from '@/stores/library'
import { useAuthStore } from '@/stores/auth'
import { useNotifications } from '@/composables'
import type { CreateDanmakuData, CreateReplyData } from '@/utils/apiClient'

interface Props {
  documentId: number
  currentPage: number | null
  pinPosition: { x: number; y: number; pageNumber: number } | null
  danmakuId: number | null
}

interface Emits {
  (e: 'close'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const libraryStore = useLibraryStore()
const authStore = useAuthStore()
const notify = useNotifications()

// Show panel when pin is placed or clicked
const showPanel = computed(() => !!props.pinPosition || !!props.danmakuId)
const newComment = ref('')
const replyingTo = ref<number | null>(null)
const replyContent = ref('')
const creatingComment = ref(false)
const creatingReply = ref<Record<number, boolean>>({})
const deletingDanmaku = ref<Record<number, boolean>>({})
const deletingReply = ref<Record<number, boolean>>({})

// Get danmaku for current context
const displayedDanmaku = computed(() => {
  if (props.danmakuId) {
    // Show comments for specific pin (danmaku)
    const danmaku = libraryStore.danmaku.find((d) => d.id === props.danmakuId)
    return danmaku ? [danmaku] : []
  }
  if (props.pinPosition && props.currentPage) {
    // Show all comments for current page when placing new pin
    return libraryStore.danmakuForPage(props.currentPage)
  }
  return []
})

// Watch for page/danmaku changes
watch(
  () => [props.currentPage, props.danmakuId],
  async ([page, danmakuId]) => {
    if (page) {
      await libraryStore.fetchDanmaku(page)
    }
    if (danmakuId) {
      // Fetch replies for the selected danmaku
      await libraryStore.fetchReplies(danmakuId)
    }
  },
  { immediate: true }
)

// Create danmaku comment at pin position
async function createComment() {
  if (!newComment.value.trim() || !props.currentPage || creatingComment.value) return
  if (!props.pinPosition) return

  const data: CreateDanmakuData = {
    content: newComment.value.trim(),
    page_number: props.pinPosition.pageNumber,
    position_x: Math.round(props.pinPosition.x),
    position_y: Math.round(props.pinPosition.y),
  }

  creatingComment.value = true
  try {
    await libraryStore.createDanmakuComment(data)
    newComment.value = ''
    notify.success('评论已添加')
    // Refresh danmaku to show new pin
    await libraryStore.fetchDanmaku(props.pinPosition.pageNumber)
    // Close panel after creating comment (temporary pin will be replaced by real pin)
    emit('close')
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

// Delete danmaku (only allowed for comment creator or admin)
async function deleteDanmaku(danmakuId: number) {
  if (deletingDanmaku.value[danmakuId]) return
  
  // Double-check permission before attempting deletion
  const danmaku = displayedDanmaku.value.find((d) => d.id === danmakuId)
  if (!danmaku || !canDeleteDanmaku(danmaku)) {
    notify.error('只能删除自己的评论')
    return
  }
  
  deletingDanmaku.value[danmakuId] = true
  try {
    await libraryStore.removeDanmaku(danmakuId)
    notify.success('评论已删除')
    // Refresh danmaku list
    if (props.currentPage) {
      await libraryStore.fetchDanmaku(props.currentPage)
    }
    // If this was the selected danmaku, close panel
    if (props.danmakuId === danmakuId) {
      emit('close')
    }
  } catch (error) {
    // Handle permission errors specifically
    const errorMessage = error instanceof Error ? error.message : '删除评论失败'
    if (errorMessage.includes('permission') || errorMessage.includes('权限') || errorMessage.includes('don\'t have permission')) {
      notify.error('只能删除自己的评论')
    } else {
      notify.error(errorMessage)
    }
    console.error('[CommentPanel] Failed to delete danmaku:', error)
  } finally {
    deletingDanmaku.value[danmakuId] = false
  }
}

// Check if current user owns the danmaku
function isOwnDanmaku(danmaku: { user_id: number }) {
  if (!authStore.user?.id) return false
  return Number(authStore.user.id) === danmaku.user_id
}

// Check if current user can delete danmaku (owner or admin)
function canDeleteDanmaku(danmaku: { user_id: number }) {
  if (!authStore.user?.id) return false
  const userId = Number(authStore.user.id)
  const isOwner = userId === danmaku.user_id
  const isAdmin = authStore.isAdmin
  return isOwner || isAdmin
}

// Check if current user can delete reply (owner or admin)
function canDeleteReply(reply: { user_id: number }) {
  if (!authStore.user?.id) return false
  const userId = Number(authStore.user.id)
  const isOwner = userId === reply.user_id
  const isAdmin = authStore.isAdmin
  return isOwner || isAdmin
}

// Delete reply (only allowed for reply creator or admin)
async function deleteReply(replyId: number, danmakuId: number) {
  if (deletingReply.value[replyId]) return
  
  // Get reply to check permission
  const replies = libraryStore.replies[danmakuId] || []
  const reply = replies.find((r) => r.id === replyId)
  if (!reply || !canDeleteReply(reply)) {
    notify.error('只能删除自己的回复')
    return
  }
  
  deletingReply.value[replyId] = true
  try {
    await libraryStore.removeReply(replyId, danmakuId)
    notify.success('回复已删除')
    // Replies are automatically removed from store by removeReply
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '删除回复失败'
    if (errorMessage.includes('permission') || errorMessage.includes('权限') || errorMessage.includes('don\'t have permission')) {
      notify.error('只能删除自己的回复')
    } else {
      notify.error(errorMessage)
    }
    console.error('[CommentPanel] Failed to delete reply:', error)
  } finally {
    deletingReply.value[replyId] = false
  }
}

// Close panel
function closePanel() {
  emit('close')
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
          {{ danmakuId ? '评论' : pinPosition ? '添加评论' : `第 ${currentPage} 页评论` }}
        </h3>
        <p
          v-if="pinPosition"
          class="text-xs text-stone-500 mt-1"
        >
          点击位置: ({{ Math.round(pinPosition.x) }}, {{ Math.round(pinPosition.y) }})
        </p>
      </div>
      <ElButton
        text
        circle
        size="small"
        @click="closePanel"
      >
        <X class="w-4 h-4" />
      </ElButton>
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
            <div class="flex items-center gap-2">
              <ElButton
                text
                size="small"
                :class="{ 'text-red-500': danmaku.is_liked }"
                @click="toggleLike(danmaku.id)"
              >
                <Heart
                  :class="['w-4 h-4 mr-1', danmaku.is_liked ? 'fill-current' : '']"
                />
                <span>{{ danmaku.likes_count }}</span>
              </ElButton>
              <ElButton
                text
                size="small"
                @click="startReply(danmaku.id)"
              >
                <MessageSquare class="w-4 h-4 mr-1" />
                <span>回复</span>
              </ElButton>
              <ElButton
                v-if="canDeleteDanmaku(danmaku)"
                text
                size="small"
                type="danger"
                :loading="deletingDanmaku[danmaku.id]"
                @click="deleteDanmaku(danmaku.id)"
              >
                <Trash2 class="w-4 h-4 mr-1" />
                <span>删除</span>
              </ElButton>
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
            class="flex items-start gap-2 text-xs text-stone-600"
          >
            <div class="flex-1">
              <span class="font-medium">{{ reply.user.name || '匿名' }}:</span>
              <span class="ml-1">{{ reply.content }}</span>
            </div>
            <ElButton
              v-if="canDeleteReply(reply)"
              text
              size="small"
              type="danger"
              :loading="deletingReply[reply.id]"
              @click="deleteReply(reply.id, danmaku.id)"
            >
              <Trash2 class="w-3 h-3" />
            </ElButton>
          </div>
        </div>

        <!-- Reply Input -->
        <div
          v-if="replyingTo === danmaku.id"
          class="ml-6 mt-2 flex gap-2"
        >
          <ElInput
            v-model="replyContent"
            placeholder="输入回复..."
            size="small"
            @keyup.enter="submitReply(danmaku.id)"
          />
          <ElButton
            type="primary"
            size="small"
            :loading="creatingReply[danmaku.id]"
            @click="submitReply(danmaku.id)"
          >
            发送
          </ElButton>
          <ElButton
            size="small"
            @click="cancelReply"
          >
            取消
          </ElButton>
        </div>
      </div>

      <div
        v-if="!libraryStore.danmakuLoading && displayedDanmaku.length === 0"
        class="text-center text-stone-400 text-sm py-8"
      >
        暂无评论
      </div>
    </div>

    <!-- Comment Input - Only show when placing new pin -->
    <div
      v-if="authStore.isAuthenticated && currentPage && pinPosition"
      class="border-t border-stone-200 p-4"
    >
      <div class="flex gap-2">
        <ElInput
          v-model="newComment"
          placeholder="添加评论..."
          @keyup.enter="createComment"
        />
        <ElButton
          type="primary"
          :loading="creatingComment"
          @click="createComment"
        >
          <Send class="w-4 h-4" />
        </ElButton>
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
