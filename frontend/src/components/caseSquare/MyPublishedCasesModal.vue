<script setup lang="ts">
import { ref, watch } from 'vue'

import { ElMessageBox } from 'element-plus'

import { Eye, FileText, Heart, PenLine, Trash2, Undo2, X } from '@lucide/vue'

import {
  caseTypeShortLabel,
  getCoverColor,
  type CaseSquareCaseType,
} from '@/components/caseSquare/caseSquareShared'
import { useLanguage, useNotifications } from '@/composables'
import {
  postCanDelist,
  postCanResubmit,
  postCanWithdraw,
} from '@/composables/caseSquare/caseSquareAuthorManage'
import {
  type CaseSquarePost,
  delistCaseSquarePost,
  getCaseSquarePosts,
  withdrawCaseSquarePost,
} from '@/utils/apiClient'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'open', post: CaseSquarePost): void
  (e: 'edit', postId: string): void
  (e: 'updated', post: CaseSquarePost): void
  (e: 'deleted', postId: string): void
}>()

const { t } = useLanguage()
const notify = useNotifications()

const posts = ref<CaseSquarePost[]>([])
const isLoading = ref(false)
const actingPostId = ref<string | null>(null)

function statusClass(status: CaseSquarePost['status']): string {
  if (status === 'approved') return 'bg-green-50 text-green-600'
  if (status === 'pending') return 'bg-amber-50 text-amber-600'
  if (status === 'withdrawn') return 'bg-gray-100 text-gray-500'
  return 'bg-red-50 text-red-600'
}

function statusText(status: CaseSquarePost['status']): string {
  if (status === 'approved') return String(t('caseSquare.status.approved'))
  if (status === 'pending') return String(t('caseSquare.status.pending'))
  if (status === 'withdrawn') return String(t('caseSquare.status.withdrawn'))
  return String(t('caseSquare.status.rejected'))
}

function caseTypeText(caseType: CaseSquareCaseType): string {
  if (caseType === 'teaching_design') return String(t('caseSquare.type.teachingDesign'))
  if (caseType === 'diagram_case') return String(t('caseSquare.type.diagramCase'))
  return String(t('caseSquare.type.diagramTemplate'))
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}

async function loadPosts() {
  isLoading.value = true
  try {
    const res = await getCaseSquarePosts({ page: 1, pageSize: 100, mine: true, sort: 'newest' })
    posts.value = res.posts
  } catch {
    posts.value = []
  } finally {
    isLoading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) void loadPosts()
  }
)

function close() {
  emit('update:visible', false)
}

function openPost(post: CaseSquarePost) {
  emit('open', post)
  close()
}

async function confirmAction(
  titleKey: string,
  messageKey: string,
  title: string
): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      String(t(messageKey, { title })),
      String(t(titleKey)),
      {
        confirmButtonText: String(t('caseSquare.detail.confirm')),
        cancelButtonText: String(t('caseSquare.detail.cancel')),
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    return true
  } catch {
    return false
  }
}

async function withdrawPost(post: CaseSquarePost) {
  if (!postCanWithdraw(post)) return
  if (!(await confirmAction('caseSquare.detail.withdrawTitle', 'caseSquare.detail.withdrawConfirm', post.title))) {
    return
  }
  actingPostId.value = post.id
  try {
    await withdrawCaseSquarePost(post.id)
    notify.success(t('caseSquare.withdrawn'))
    posts.value = posts.value.filter((p) => p.id !== post.id)
    emit('deleted', post.id)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  } finally {
    actingPostId.value = null
  }
}

async function delistPost(post: CaseSquarePost) {
  if (!postCanDelist(post)) return
  if (!(await confirmAction('caseSquare.detail.delistTitle', 'caseSquare.detail.delistConfirm', post.title))) {
    return
  }
  actingPostId.value = post.id
  try {
    const res = await delistCaseSquarePost(post.id)
    notify.success(t('caseSquare.delisted'))
    const idx = posts.value.findIndex((p) => p.id === post.id)
    if (idx >= 0) posts.value[idx] = res.post
    emit('updated', res.post)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  } finally {
    actingPostId.value = null
  }
}

function resubmitPost(post: CaseSquarePost) {
  if (!postCanResubmit(post)) return
  emit('edit', post.id)
  close()
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="close"
    >
      <div class="mx-6 w-full max-w-3xl rounded-2xl bg-white shadow-2xl">
        <div class="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div>
            <h2 class="text-lg font-bold text-gray-900">{{ t('caseSquare.myCasesModalTitle') }}</h2>
            <p class="mt-0.5 text-xs text-gray-400">{{ t('caseSquare.myCasesManageHint') }}</p>
          </div>
          <button
            type="button"
            class="my-cases-modal-close"
            @click="close"
          >
            <X class="h-5 w-5" />
          </button>
        </div>

        <div class="max-h-[70vh] overflow-y-auto px-6 py-4">
          <div v-if="isLoading" class="py-12 text-center text-sm text-gray-400">…</div>
          <div v-else-if="posts.length === 0" class="py-12 text-center">
            <FileText class="mx-auto mb-3 h-12 w-12 text-gray-300" />
            <p class="text-sm text-gray-400">{{ t('caseSquare.myCasesEmpty') }}</p>
            <p class="mt-1 text-xs text-gray-300">{{ t('caseSquare.myCasesEmptyHint') }}</p>
          </div>
          <div v-else class="divide-y divide-gray-100">
            <div
              v-for="post in posts"
              :key="post.id"
              class="flex items-center gap-3 rounded-xl px-1 py-1 transition-colors hover:bg-gray-50"
            >
              <button
                type="button"
                class="my-cases-row-btn"
                @click="openPost(post)"
              >
                <div
                  :class="[
                    'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white',
                    `bg-gradient-to-br ${getCoverColor(post.id)}`,
                  ]"
                >
                  {{ caseTypeShortLabel(post.case_type) }}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="truncate text-sm font-medium text-gray-900">{{ post.title }}</span>
                    <span
                      class="shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium"
                      :class="statusClass(post.status)"
                    >
                      {{ statusText(post.status) }}
                    </span>
                  </div>
                  <div class="mt-0.5 flex flex-wrap items-center gap-3 text-xs text-gray-400">
                    <span>{{ caseTypeText(post.case_type) }}</span>
                    <span v-if="post.subject">{{ post.subject }}</span>
                    <span>{{ formatDate(post.created_at) }}</span>
                    <span class="inline-flex items-center gap-1">
                      <Eye class="h-3 w-3" />
                      {{ post.views_count }}
                    </span>
                    <span
                      v-if="post.status === 'approved'"
                      class="inline-flex items-center gap-1"
                    >
                      <Heart class="h-3 w-3" />
                      {{ post.likes_count }}
                    </span>
                  </div>
                  <p v-if="post.status === 'rejected' && post.rejection_reason" class="mt-1 text-xs text-red-500">
                    {{ post.rejection_reason }}
                  </p>
                </div>
              </button>

              <div
                class="flex shrink-0 flex-wrap items-center justify-end gap-1.5"
                @click.stop
              >
                <button
                  v-if="postCanResubmit(post)"
                  type="button"
                  class="my-cases-action-btn my-cases-action-btn--primary"
                  :disabled="actingPostId === post.id"
                  @click="resubmitPost(post)"
                >
                  <PenLine class="h-3.5 w-3.5" />
                  {{ t('caseSquare.myCasesAction.edit') }}
                </button>
                <button
                  v-if="postCanWithdraw(post)"
                  type="button"
                  class="my-cases-action-btn my-cases-action-btn--withdraw"
                  :disabled="actingPostId === post.id"
                  @click="withdrawPost(post)"
                >
                  <Undo2 class="h-3.5 w-3.5" />
                  {{ t('caseSquare.detail.withdraw') }}
                </button>
                <button
                  v-if="postCanDelist(post)"
                  type="button"
                  class="my-cases-action-btn my-cases-action-btn--delist"
                  :disabled="actingPostId === post.id"
                  @click="delistPost(post)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                  {{ t('caseSquare.detail.delist') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.my-cases-modal-close {
  border: none;
  outline: none;
  border-radius: 0.5rem;
  padding: 0.25rem;
  color: #9ca3af;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.my-cases-modal-close:hover {
  background: #f3f4f6;
  color: #4b5563;
}

.my-cases-modal-close:focus,
.my-cases-modal-close:focus-visible {
  outline: none;
  box-shadow: none;
}

.my-cases-row-btn {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  text-align: left;
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  border-radius: 0.75rem;
}

.my-cases-row-btn:focus,
.my-cases-row-btn:focus-visible {
  outline: none;
  box-shadow: none;
}

.my-cases-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border-radius: 0.5rem;
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  font-weight: 500;
  border: none;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.my-cases-action-btn:focus,
.my-cases-action-btn:focus-visible {
  outline: none;
  box-shadow: none;
}

.my-cases-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.my-cases-action-btn--primary {
  background: #111827;
  color: #fff;
}

.my-cases-action-btn--primary:hover:not(:disabled) {
  background: #1f2937;
}

.my-cases-action-btn--withdraw {
  background: #fffbeb;
  color: #b45309;
}

.my-cases-action-btn--withdraw:hover:not(:disabled) {
  background: #fef3c7;
}

.my-cases-action-btn--delist {
  background: #fef2f2;
  color: #dc2626;
}

.my-cases-action-btn--delist:hover:not(:disabled) {
  background: #fee2e2;
}
</style>
