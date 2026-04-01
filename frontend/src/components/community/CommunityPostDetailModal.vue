<script setup lang="ts">
/**
 * CommunityPostDetailModal - Instagram/Facebook style post detail
 * Image on left (clickable, zoom to fit, click to zoom); right panel: user info + comments
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import {
  ElDialog,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElMessageBox,
  ElScrollbar,
} from 'element-plus'

import { Download, Heart, MoreVertical, Trash2, X } from 'lucide-vue-next'

import MindmateInput from '@/components/panels/mindmate/MindmateInput.vue'
import { useLanguage, useNotifications } from '@/composables'
import type { LocaleCode } from '@/i18n/locales'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useAuthStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import {
  type CommunityPost,
  type CommunityPostComment,
  createCommunityPostComment,
  deleteCommunityPostComment,
  getCommunityPost,
  getCommunityPostComments,
  getCommunityPostLikes,
  toggleCommunityPostLike,
} from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
  postId: string | null
  postPreview?: CommunityPost | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'likeToggled', post: CommunityPost): void
}>()

const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const { t, currentLanguage } = useLanguage()
const notify = useNotifications()

const post = ref<CommunityPost | null>(null)
const comments = ref<CommunityPostComment[]>([])
const totalComments = ref(0)
const likerNames = ref<string[]>([])
const likesTotal = ref(0)
const isLoading = ref(false)
const isCommentsLoading = ref(false)
const newComment = ref('')
const isSubmittingComment = ref(false)
const showImageZoom = ref(false)
const isImporting = ref(false)
const commentInputRef = ref<HTMLElement | null>(null)

const canComment = computed(() => authStore.isAuthenticated)

const likesDisplayText = computed(() => {
  if (likesTotal.value === 0) return ''
  const names = likerNames.value
  if (names.length === 0) {
    return t('community.post.likesTotal', { n: likesTotal.value })
  }
  const sep = currentLanguage.value === 'zh' ? '、' : ', '
  const nameList = names.join(sep)
  if (likesTotal.value <= names.length) {
    return t('community.post.likesListed', { names: nameList })
  }
  return t('community.post.likesWithOthers', {
    names: nameList,
    others: likesTotal.value - names.length,
    total: likesTotal.value,
  })
})

async function loadPost() {
  if (!props.postId) return
  isLoading.value = true
  try {
    post.value = await getCommunityPost(props.postId)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to load post')
    close()
  } finally {
    isLoading.value = false
  }
}

async function loadComments() {
  if (!props.postId) return
  isCommentsLoading.value = true
  try {
    const res = await getCommunityPostComments(props.postId, 1, 100)
    comments.value = res.comments
    totalComments.value = res.total
  } catch {
    comments.value = []
  } finally {
    isCommentsLoading.value = false
  }
}

async function loadLikes() {
  if (!props.postId) return
  try {
    const res = await getCommunityPostLikes(props.postId, 5)
    likerNames.value = res.names
    likesTotal.value = res.total
  } catch {
    likerNames.value = []
    likesTotal.value = 0
  }
}

function handleMenuCommand(cmd: string) {
  if (cmd === 'like') toggleLike()
  else if (cmd === 'import') importToLibrary()
}

watch(
  () => [props.visible, props.postId] as const,
  ([visible, id]) => {
    if (visible && id) {
      post.value = props.postPreview ?? null
      comments.value = []
      totalComments.value = 0
      likerNames.value = []
      likesTotal.value = 0
      newComment.value = ''
      showImageZoom.value = false
      loadPost().then(() => {
        loadComments()
        loadLikes()
      })
    }
  }
)

function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape') showImageZoom.value = false
}
watch(showImageZoom, (open) => {
  if (open) {
    window.addEventListener('keydown', onEscape)
  } else {
    window.removeEventListener('keydown', onEscape)
  }
})
onUnmounted(() => window.removeEventListener('keydown', onEscape))

function close() {
  emit('update:visible', false)
}

async function toggleLike() {
  if (!post.value || !authStore.isAuthenticated) return
  try {
    const res = await toggleCommunityPostLike(post.value.id)
    post.value.is_liked = res.is_liked
    post.value.likes_count = res.likes_count
    emit('likeToggled', post.value)
    loadLikes()
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to toggle like')
  }
}

async function importToLibrary() {
  const p = post.value
  if (!p || !authStore.isAuthenticated) {
    notify.warning(t('community.post.loginFirst'))
    return
  }
  const fullPost = p as CommunityPost & { spec?: unknown }
  const spec = fullPost.spec as Record<string, unknown> | undefined
  if (!spec || typeof spec !== 'object') {
    notify.error(t('community.post.diagramLoadFailed'))
    return
  }
  isImporting.value = true
  try {
    const saved = await savedDiagramsStore.saveDiagram(p.title, p.diagram_type, spec, 'zh', null)
    if (saved) {
      savedDiagramsStore.setActiveDiagram(saved.id)
      notify.success(t('community.post.importOk'))
    } else if (savedDiagramsStore.error) {
      notify.error(savedDiagramsStore.error)
    } else {
      notify.error(t('community.post.importFull'))
    }
  } catch (e) {
    notify.error(e instanceof Error ? e.message : t('community.post.importFail'))
  } finally {
    isImporting.value = false
  }
}

async function submitComment() {
  const content = newComment.value.trim()
  if (!content || !props.postId || !authStore.isAuthenticated) return
  isSubmittingComment.value = true
  try {
    const res = await createCommunityPostComment(props.postId, content)
    const newCommentWithDelete = { ...res.comment, can_delete: true }
    comments.value = [...comments.value, newCommentWithDelete]
    totalComments.value += 1
    if (post.value) {
      post.value.comments_count = totalComments.value
    }
    newComment.value = ''
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to add comment')
  } finally {
    isSubmittingComment.value = false
  }
}

const deletingCommentId = ref<number | null>(null)

async function deleteComment(comment: CommunityPostComment) {
  if (!props.postId || !comment.can_delete) return
  try {
    await ElMessageBox.confirm(
      t('community.post.deleteCommentConfirm'),
      t('community.post.deleteCommentTitle'),
      {
        type: 'warning',
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }
  deletingCommentId.value = comment.id
  try {
    await deleteCommunityPostComment(props.postId, comment.id)
    comments.value = comments.value.filter((c) => c.id !== comment.id)
    totalComments.value = Math.max(0, totalComments.value - 1)
    if (post.value) {
      post.value.comments_count = totalComments.value
    }
    notify.success(t('community.post.commentDeleted'))
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed to delete comment')
  } finally {
    deletingCommentId.value = null
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 60) return t('community.time.minutesAgo', { n: diffMins })
  if (diffHours < 24) return t('community.time.hoursAgo', { n: diffHours })
  if (diffDays < 7) return t('community.time.daysAgo', { n: diffDays })
  return d.toLocaleDateString(intlLocaleForUiCode(currentLanguage.value as LocaleCode))
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="undefined"
    width="min(900px, 95vw)"
    class="community-post-detail-modal"
    :show-close="true"
    destroy-on-close
    @close="close"
    @update:model-value="emit('update:visible', $event)"
  >
    <div
      v-if="isLoading"
      class="detail-loading flex items-center justify-center py-20"
    >
      <span class="text-stone-400">{{ t('common.loading') }}</span>
    </div>

    <div
      v-else-if="post"
      class="detail-content flex flex-col md:flex-row"
    >
      <!-- Left: image + footer (likes + menu below image) -->
      <div class="detail-image-column md:w-1/2 flex flex-col">
        <!-- Image: clickable, top overlay (name/org/time) only -->
        <div
          class="detail-image-wrapper bg-stone-100 relative flex items-stretch min-h-[280px] md:min-h-[420px] overflow-hidden cursor-zoom-in"
          @click="post.thumbnail_url && (showImageZoom = true)"
        >
          <img
            v-if="post.thumbnail_url"
            :src="post.thumbnail_url"
            :alt="post.title"
            class="detail-image w-full h-full object-cover object-center select-none"
            draggable="false"
          />
          <div
            v-else
            class="text-stone-400 text-sm"
          >
            {{ t('community.post.noPreview') }}
          </div>

          <!-- Top-left: name · organization · time (no avatar) -->
          <div
            class="absolute top-0 left-0 right-0 p-3 bg-gradient-to-b from-black/50 to-transparent pointer-events-none"
          >
            <div class="flex items-center gap-2 text-sm text-white/95">
              <span class="font-medium truncate">
                {{ post.author.name ?? 'Anonymous' }}
              </span>
              <template v-if="post.author.organization">
                <span class="opacity-80">·</span>
                <span class="truncate opacity-90">
                  {{ post.author.organization }}
                </span>
              </template>
              <span class="opacity-80">·</span>
              <span class="shrink-0 opacity-90">
                {{ formatDate(post.created_at) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Below image: likes (cute text) + menu icon -->
        <div
          class="detail-image-footer flex items-center justify-between gap-3 px-3 py-2 bg-stone-50 border-t border-stone-200"
        >
          <p
            v-if="likesDisplayText"
            class="detail-likes-text text-xs text-stone-500 truncate flex-1 min-w-0"
          >
            {{ likesDisplayText }}
          </p>
          <p
            v-else
            class="detail-likes-text text-xs text-stone-400 flex-1"
          >
            {{ t('community.post.noLikes') }}
          </p>
          <ElDropdown
            trigger="click"
            placement="top-end"
            @command="handleMenuCommand"
          >
            <button
              class="w-8 h-8 rounded-full flex items-center justify-center text-stone-500 hover:bg-stone-200 hover:text-stone-700 transition-colors shrink-0"
              aria-label="Menu"
            >
              <MoreVertical class="w-5 h-5" />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem command="like">
                  <Heart
                    :class="[
                      'w-4 h-4 mr-2 shrink-0',
                      post.is_liked ? 'text-rose-500' : 'text-stone-400',
                    ]"
                  />
                  {{ post.is_liked ? t('community.post.unlike') : t('community.post.like') }}
                </ElDropdownItem>
                <ElDropdownItem
                  command="import"
                  :disabled="!authStore.isAuthenticated || isImporting"
                >
                  <Download class="w-4 h-4 mr-2 shrink-0 text-stone-400" />
                  {{ t('community.post.importAction') }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>
        </div>
      </div>

      <!-- Image zoom lightbox -->
      <Teleport to="body">
        <Transition name="fade">
          <div
            v-if="showImageZoom && post?.thumbnail_url"
            class="image-zoom-overlay fixed inset-0 z-[9999] bg-black/90 flex items-center justify-center cursor-zoom-out"
            @click.self="showImageZoom = false"
          >
            <button
              class="absolute top-4 right-4 w-10 h-10 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-colors"
              aria-label="Close"
              @click="showImageZoom = false"
            >
              <X class="w-5 h-5" />
            </button>
            <img
              :src="post.thumbnail_url"
              :alt="post.title"
              class="max-w-[95vw] max-h-[95vh] object-contain pointer-events-none"
              draggable="false"
              @click.stop
            />
          </div>
        </Transition>
      </Teleport>

      <!-- Right: description + comments -->
      <div class="detail-panel md:w-1/2 flex flex-col min-h-0">
        <!-- Comments scroll area -->
        <el-scrollbar class="detail-comments-scroll flex-1">
          <div class="detail-comments px-4 pt-2 pb-3 space-y-4">
            <!-- Title + uploader's description (no duplicate user info) -->
            <div
              v-if="post.title || post.description"
              class="comment-item comment-uploader"
            >
              <h3
                v-if="post.title"
                class="font-semibold text-stone-800 text-sm mb-2"
              >
                {{ post.title }}
              </h3>
              <p
                v-if="post.description"
                class="text-sm text-stone-600 leading-relaxed whitespace-pre-wrap"
              >
                {{ post.description }}
              </p>
            </div>

            <!-- Other users' comments -->
            <div
              v-for="c in comments"
              :key="c.id"
              class="comment-item"
            >
              <div class="flex gap-3">
                <div
                  class="w-8 h-8 rounded-full bg-stone-100 flex items-center justify-center text-sm shrink-0"
                >
                  {{ c.author.avatar ?? '👤' }}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-baseline gap-2 mb-1">
                    <span class="font-semibold text-stone-800 text-sm">
                      {{ c.author.name ?? 'Anonymous' }}
                    </span>
                    <span class="text-xs text-stone-400">
                      {{ formatDate(c.created_at) }}
                    </span>
                    <button
                      v-if="c.can_delete"
                      type="button"
                      class="ml-auto shrink-0 p-1 rounded text-stone-400 hover:text-rose-500 hover:bg-rose-50 transition-colors"
                      :disabled="deletingCommentId === c.id"
                      :aria-label="t('community.post.deleteCommentTitle')"
                      @click="deleteComment(c)"
                    >
                      <Trash2 class="w-4 h-4" />
                    </button>
                  </div>
                  <p class="text-sm text-stone-600 leading-relaxed whitespace-pre-wrap">
                    {{ c.content }}
                  </p>
                </div>
              </div>
            </div>

            <div
              v-if="isCommentsLoading"
              class="text-center py-4 text-stone-400 text-sm"
            >
              {{ t('community.post.loadingComments') }}
            </div>

            <div
              v-else-if="!post.title && !post.description && comments.length === 0"
              class="text-center py-8 text-stone-400 text-sm"
            >
              {{ t('community.post.noComments') }}
            </div>
          </div>
        </el-scrollbar>

        <!-- Comment input - pinned to bottom -->
        <div
          ref="commentInputRef"
          class="detail-footer mt-auto shrink-0 border-t border-stone-100 px-4 py-4"
        >
          <MindmateInput
            v-if="canComment"
            v-model:input-text="newComment"
            mode="fullpage"
            :is-loading="isSubmittingComment"
            :show-file-upload="false"
            :show-suggestions="false"
            :placeholder="t('community.post.commentPlaceholder')"
            :maxlength="120"
            @send="submitComment"
          />
          <p
            v-else
            class="text-xs text-stone-400"
          >
            {{ t('community.post.loginToComment') }}
          </p>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.community-post-detail-modal :deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

.community-post-detail-modal :deep(.el-dialog__header) {
  padding: 0;
  margin: 0;
  min-height: 0;
}

.community-post-detail-modal :deep(.el-dialog__header) .el-dialog__title {
  display: none;
}

.community-post-detail-modal :deep(.el-dialog__body) {
  padding: 0;
  max-height: 85vh;
}

.community-post-detail-modal :deep(.el-dialog__headerbtn) {
  top: 12px;
  inset-inline-end: 12px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  width: 32px;
  height: 32px;
}

.detail-content {
  max-height: 85vh;
  overflow: hidden;
}

@media (min-width: 768px) {
  .detail-content {
    min-height: 420px;
  }
}

.detail-image-column {
  border-radius: 0;
}

.detail-image-wrapper {
  border: 3px solid #e7e5e4;
  border-radius: 0;
}

.detail-image-wrapper .detail-image {
  border-radius: 0;
}

.detail-image-footer {
  border-color: #e7e5e4;
}

.detail-likes-text {
  font-size: 12px;
  color: #78716c;
  line-height: 1.4;
  letter-spacing: 0.01em;
}

.detail-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.detail-comments-scroll {
  flex: 1;
  min-height: 0;
}

.comment-item {
  padding: 4px 0;
}

.comment-uploader {
  padding-bottom: 12px;
  border-bottom: 1px solid #f5f5f4;
  margin-bottom: 4px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* MindmateInput uses fullpage mode - compact padding for modal */
.community-post-detail-modal .input-area-fullpage {
  padding: 12px 0 0;
  max-width: none;
  margin: 0;
}
</style>
