<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useRouter } from 'vue-router'

import { ElMessageBox } from 'element-plus'

import {
  Award,
  Download,
  Eye,
  Heart,
  LayoutTemplate,
  MessageCircle,
  PenLine,
  Star,
  Tag,
  Trash2,
  Undo2,
  X,
} from '@lucide/vue'

import ShowcaseDiagramPreview from '@/components/showcase/ShowcaseDiagramPreview.vue'
import ShowcaseTeachingDocPreview from '@/components/showcase/ShowcaseTeachingDocPreview.vue'
import {
  caseTypeEmoji,
  caseTypeTheme,
  type ShowcaseCaseType,
} from '@/components/showcase/showcaseShared'
import { useLanguage, useNotifications } from '@/composables'
import {
  postCanDelist,
  postCanResubmit,
  postCanWithdraw,
} from '@/composables/showcase/showcaseAuthorManage'
import { resolveDevStaticUrl } from '@/utils/devStaticUrl'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useShowcaseDiagramAction } from '@/composables/showcase/useShowcaseDiagramAction'
import { useAuthStore } from '@/stores'
import {
  type ShowcasePost,
  deleteAdminShowcasePost,
  deleteShowcasePost,
  delistShowcasePost,
  getShowcasePost,
  reviewAdminShowcasePost,
  reviewShowcasePost,
  toggleShowcaseExpertRecommend,
  toggleShowcasePostFavorite,
  toggleShowcasePostLike,
  withdrawShowcasePost,
} from '@/utils/apiClient'

type TeachingSpec = {
  body?: string
  design_highlights?: string[] | string
  teaching_reflection?: string
  attachment_path?: string
  attachment_filename?: string
}

type DiagramSpec = {
  classroom_application?: string
}

type TeachingTab = 'intro' | 'highlights' | 'reflection'
type DiagramTab = 'intro' | 'classroomApp'

const TEACHING_TABS: TeachingTab[] = ['intro', 'highlights', 'reflection']
const DIAGRAM_TABS: DiagramTab[] = ['intro', 'classroomApp']

const props = withDefaults(
  defineProps<{
    visible: boolean
    postId: string | null
    postPreview?: ShowcasePost | null
    /** public = Showcase browse; admin = management panel moderation */
    mode?: 'public' | 'admin'
    /** Published-case admin: recommend toggle + confirmed delete */
    publishedManage?: boolean
  }>(),
  {
    mode: 'public',
    publishedManage: false,
  }
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'updated', post: ShowcasePost): void
  (e: 'deleted'): void
  (e: 'edit', postId: string): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const { can: adminCan } = useAdminAccess()
const router = useRouter()
const {
  actionLabel,
  resolveActionForPost,
  handleDiagramAction,
  isImporting,
} = useShowcaseDiagramAction()

const post = ref<ShowcasePost | null>(null)
const isLoading = ref(false)
const loadError = ref<string | null>(null)
const rejectReason = ref('')
const showRejectInput = ref(false)
const teachingTab = ref<TeachingTab>('intro')
const diagramTab = ref<DiagramTab>('intro')

const isTeachingDesign = computed(() => post.value?.case_type === 'teaching_design')

const diagramAction = computed(() => {
  if (!post.value || isTeachingDesign.value) return null
  return resolveActionForPost(post.value, diagramPostSpec.value)
})

const diagramActionLabel = computed(() => actionLabel(diagramAction.value))

const diagramActionIcon = computed(() => {
  if (diagramAction.value === 'go_draw') return PenLine
  if (diagramAction.value === 'apply_template') return LayoutTemplate
  return Download
})

const teachingTheme = computed(() => caseTypeTheme('teaching_design'))

const diagramTheme = computed(() =>
  post.value ? caseTypeTheme(post.value.case_type) : caseTypeTheme('diagram_case')
)

const teachingSpec = computed((): TeachingSpec => {
  const full = post.value as (ShowcasePost & { spec?: TeachingSpec }) | null
  return full?.spec && typeof full.spec === 'object' ? full.spec : {}
})

const diagramPostSpec = computed(() => {
  const full = post.value as (ShowcasePost & { spec?: unknown }) | null
  return full?.spec ?? null
})

const introText = computed(() => {
  const body = teachingSpec.value.body
  if (typeof body === 'string' && body.trim()) return body.trim()
  return post.value?.description?.trim() ?? ''
})

const diagramIntroText = computed(() => post.value?.description?.trim() ?? '')

const classroomAppText = computed(() => {
  const full = diagramPostSpec.value
  if (!full || typeof full !== 'object') return ''
  const app = (full as DiagramSpec).classroom_application
  return typeof app === 'string' && app.trim() ? app.trim() : ''
})

const highlightsList = computed(() => {
  const raw = teachingSpec.value.design_highlights
  if (Array.isArray(raw)) return raw.map((s) => String(s).trim()).filter(Boolean)
  if (typeof raw === 'string' && raw.trim()) {
    return raw
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
})

const docFallbackText = computed(() => introText.value)

const reflectionText = computed(() => {
  const reflection = teachingSpec.value.teaching_reflection
  if (typeof reflection === 'string' && reflection.trim()) return reflection.trim()
  return ''
})

const displayTags = computed(() =>
  (post.value?.tags ?? []).filter((tag) => tag !== 'demo_seed_v1')
)

const isAdminMode = computed(() => props.mode === 'admin')

const isOwnPost = computed(() => {
  const p = post.value
  const userId = authStore.user?.id
  if (!p || !userId) return false
  return String(p.author?.id) === String(userId)
})

const showPublicInteractions = computed(
  () => !isAdminMode.value && post.value?.status === 'approved'
)

const showAuthorWithdraw = computed(
  () => !isAdminMode.value && post.value && postCanWithdraw(post.value, isOwnPost.value)
)

const showAuthorDelist = computed(
  () => !isAdminMode.value && post.value && postCanDelist(post.value, isOwnPost.value)
)

const showAuthorResubmit = computed(
  () => !isAdminMode.value && post.value && postCanResubmit(post.value, isOwnPost.value)
)

const showAuthorManageBar = computed(
  () => showAuthorWithdraw.value || showAuthorDelist.value || showAuthorResubmit.value
)

const showAuthorDelete = computed(() => false)

const showPlatformDelete = computed(
  () =>
    (isAdminMode.value || props.publishedManage) &&
    (!!post.value?.can_delete || adminCan('tab.showcase.edit'))
)

const showDeleteButton = computed(() => showPlatformDelete.value)

const showExpertRecommend = computed(
  () =>
    props.publishedManage &&
    (!!post.value?.can_expert_recommend || adminCan('tab.showcase.recommend'))
)

const showReviewActions = computed(() => {
  if (!isAdminMode.value || props.publishedManage || post.value?.status !== 'pending') return false
  return !!post.value?.can_review || adminCan('tab.showcase.edit')
})

function caseTypeLabel(caseType: ShowcaseCaseType): string {
  if (caseType === 'teaching_design') return String(t('showcase.type.teachingDesign'))
  if (caseType === 'diagram_case') return String(t('showcase.type.diagramCase'))
  return String(t('showcase.type.diagramTemplate'))
}

function teachingTabLabel(tab: TeachingTab): string {
  if (tab === 'intro') return String(t('showcase.detail.tab.intro'))
  if (tab === 'highlights') return String(t('showcase.detail.tab.highlights'))
  return String(t('showcase.detail.tab.reflection'))
}

function diagramTabLabel(tab: DiagramTab): string {
  if (tab === 'intro') return String(t('showcase.detail.tab.diagramIntro'))
  return String(t('showcase.detail.tab.classroomApp'))
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}

watch(
  () => [props.visible, props.postId] as const,
  ([visible, id]) => {
    if (!visible || !id) return
    post.value = props.postPreview ?? null
    loadError.value = null
    rejectReason.value = ''
    showRejectInput.value = false
    teachingTab.value = 'intro'
    diagramTab.value = 'intro'
    void loadPost()
  }
)

async function loadPost() {
  if (!props.postId) return
  isLoading.value = true
  loadError.value = null
  try {
    post.value = await getShowcasePost(props.postId)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(t('showcase.detail.loadFailed'))
    if (!props.postPreview) {
      loadError.value = msg
      notify.error(msg)
    }
    if (!post.value && props.postPreview) {
      post.value = props.postPreview
    }
  } finally {
    isLoading.value = false
  }
}

async function toggleLike() {
  if (!post.value) return
  try {
    const res = await toggleShowcasePostLike(post.value.id)
    post.value = { ...post.value, is_liked: res.liked, likes_count: res.likes_count }
    emit('updated', post.value)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function toggleFavorite() {
  if (!post.value || post.value.status !== 'approved') return
  try {
    const res = await toggleShowcasePostFavorite(post.value.id)
    post.value = { ...post.value, is_favorited: res.favorited }
    emit('updated', post.value)
    notify.success(
      String(
        res.favorited ? t('showcase.detail.favorited') : t('showcase.detail.unfavorited')
      ),
      2000
    )
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function toggleRecommend() {
  if (!post.value) return
  try {
    const res = await toggleShowcaseExpertRecommend(post.value.id)
    post.value = res.post
    emit('updated', post.value)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function approve() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) return
  try {
    if (isAdminMode.value) {
      await reviewAdminShowcasePost(postId, 'approve')
    } else {
      await reviewShowcasePost(postId, 'approve')
    }
    notify.success(t('showcase.detail.approved'))
    await loadPost()
    if (post.value) emit('updated', post.value)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function reject() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) return
  try {
    if (isAdminMode.value) {
      await reviewAdminShowcasePost(postId, 'reject', rejectReason.value)
    } else {
      await reviewShowcasePost(postId, 'reject', rejectReason.value)
    }
    notify.success(t('showcase.detail.rejected'))
    showRejectInput.value = false
    await loadPost()
    if (post.value) emit('updated', post.value)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function confirmAuthorAction(
  titleKey: string,
  messageKey: string
): Promise<boolean> {
  const title = post.value?.title?.trim() || post.value?.id || ''
  try {
    await ElMessageBox.confirm(
      String(t(messageKey, { title })),
      String(t(titleKey)),
      {
        confirmButtonText: String(t('showcase.detail.confirm')),
        cancelButtonText: String(t('showcase.detail.cancel')),
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    return true
  } catch {
    return false
  }
}

async function withdrawCase() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) return
  if (!(await confirmAuthorAction('showcase.detail.withdrawTitle', 'showcase.detail.withdrawConfirm'))) {
    return
  }
  try {
    await withdrawShowcasePost(postId)
    notify.success(t('showcase.withdrawn'))
    emit('deleted')
    emit('update:visible', false)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function delistCase() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) return
  if (!(await confirmAuthorAction('showcase.detail.delistTitle', 'showcase.detail.delistConfirm'))) {
    return
  }
  try {
    const res = await delistShowcasePost(postId)
    notify.success(t('showcase.delisted'))
    post.value = res.post
    emit('updated', res.post)
    emit('update:visible', false)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

function openResubmit() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) return
  emit('edit', postId)
  emit('update:visible', false)
}

async function remove() {
  const postId = (props.postId ?? post.value?.id ?? '').trim()
  if (!postId) {
    notify.error(String(t('showcase.detail.loadFailed')))
    return
  }
  if (props.publishedManage) {
    const title = post.value?.title?.trim() || postId
    try {
      await ElMessageBox.confirm(
        String(t('admin.showcase.published.deleteConfirm', { title })),
        String(t('admin.showcase.published.deleteTitle')),
        {
          confirmButtonText: String(t('admin.delete')),
          cancelButtonText: String(t('admin.cancel')),
          type: 'warning',
          confirmButtonClass: 'el-button--danger',
        }
      )
    } catch {
      return
    }
  }
  try {
    if (isAdminMode.value || props.publishedManage) {
      await deleteAdminShowcasePost(postId)
    } else {
      await deleteShowcasePost(postId)
    }
    notify.success(t('showcase.deleted'))
    emit('deleted')
    emit('update:visible', false)
  } catch (e) {
    notify.error(e instanceof Error ? e.message : 'Failed')
  }
}

async function runDiagramAction() {
  if (!post.value) return
  await handleDiagramAction(post.value, diagramPostSpec.value, { closeModal: close })
}

function askMindMate() {
  if (!post.value) return
  void router.push({
    name: 'MindMate',
    query: { q: `请帮我分析这份教学设计案例：《${post.value.title}》` },
  })
  close()
}

function close() {
  emit('update:visible', false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="close"
    >
      <div
        v-if="post"
        class="mx-6 flex w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        style="max-height: 88vh; height: 78vh"
      >
        <p
          v-if="loadError"
          class="shrink-0 border-b border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-800"
        >
          {{ loadError }}
        </p>
        <div class="flex min-h-0 flex-1 overflow-hidden">
        <!-- 教学设计：左侧文档预览 -->
        <template v-if="isTeachingDesign">
          <div class="flex w-[60%] min-w-0 flex-col border-r border-gray-100 bg-gray-50">
            <div
              :class="[
                'relative flex shrink-0 items-center justify-between px-6 py-3',
                teachingTheme.headerGradient,
              ]"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    teachingTheme.caseTypeTagClass,
                  ]"
                >
                  {{ caseTypeEmoji('teaching_design') }}{{ caseTypeLabel('teaching_design') }}
                </span>
                <span
                  v-if="post.subject"
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    teachingTheme.subjectTagClass,
                  ]"
                >
                  {{ post.subject }}
                </span>
                <span
                  v-if="post.grade"
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    teachingTheme.gradeTagClass,
                  ]"
                >
                  {{ post.grade }}
                </span>
              </div>
              <div class="flex items-center gap-3">
                <span class="flex items-center gap-1 text-[11px] text-white/80">
                  <Eye class="h-3 w-3" />
                  {{ post.views_count }}
                </span>
              </div>
            </div>

            <div class="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
              <ShowcaseTeachingDocPreview
                :attachment-url="post.attachment_url"
                :fallback-text="docFallbackText"
                :watermark-name="post.author.name"
                :watermark-organization="post.author.organization"
              />
            </div>

            <div class="shrink-0 border-t border-gray-100 bg-white px-6 py-3">
              <div class="flex items-center">
                <div class="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100 text-base">
                  {{ post.author.avatar ?? '👤' }}
                </div>
                <span class="ml-2 text-sm font-medium text-gray-900">{{ post.author.name }}</span>
                <span v-if="post.author.organization" class="ml-1 text-[11px] font-normal text-gray-400">
                  · {{ post.author.organization }}
                </span>
                <span class="ml-auto text-[11px] text-gray-400">{{ formatDate(post.created_at) }}</span>
              </div>
            </div>
          </div>

          <div class="flex w-[40%] min-w-0 flex-col">
            <div class="border-b border-gray-100 px-5 py-4">
              <div class="flex items-start justify-between gap-3">
                <h2 class="line-clamp-2 text-base font-bold leading-snug text-gray-900">
                  {{ post.title }}
                </h2>
                <button type="button" class="detail-modal-close shrink-0" @click="close">
                  <X class="h-5 w-5" />
                </button>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <button
                  v-if="showPublicInteractions"
                  type="button"
                  :class="[
                    'detail-like-btn inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
                    post.is_liked
                      ? 'bg-red-500 text-white shadow-sm hover:bg-red-600'
                      : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600',
                  ]"
                  @click="toggleLike"
                >
                  <Heart class="h-4 w-4" :class="post.is_liked ? 'fill-current' : ''" />
                  {{ post.is_liked ? t('showcase.detail.liked') : t('showcase.detail.like') }}
                  <span :class="post.is_liked ? 'text-red-100' : 'font-normal text-gray-400'">
                    {{ post.likes_count }}
                  </span>
                </button>
                <button
                  v-if="showPublicInteractions"
                  type="button"
                  :class="[
                    'detail-like-btn inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
                    post.is_favorited
                      ? 'bg-amber-500 text-white shadow-sm hover:bg-amber-600'
                      : 'bg-gray-100 text-gray-700 hover:bg-amber-50 hover:text-amber-600',
                  ]"
                  @click="toggleFavorite"
                >
                  <Star class="h-4 w-4" :class="post.is_favorited ? 'fill-current' : ''" />
                  {{ post.is_favorited ? t('showcase.detail.favorited') : t('showcase.detail.favorite') }}
                </button>
                <span
                  v-if="post.is_expert_recommended"
                  class="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-600"
                >
                  <Award class="h-3.5 w-3.5" />
                  {{ t('showcase.expertBadge') }}
                </span>
                <span class="inline-flex items-center gap-1 text-xs text-gray-400">
                  <Eye class="h-3.5 w-3.5" />
                  {{ t('showcase.detail.views', { n: post.views_count }) }}
                </span>
              </div>
            </div>

            <div
              v-if="showPublicInteractions || showDeleteButton || showExpertRecommend"
              class="flex flex-wrap gap-2 border-b border-gray-100 px-5 py-3"
            >
              <button
                v-if="showPublicInteractions"
                type="button"
                class="detail-mindmate-btn flex flex-1 items-center justify-center gap-2 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
                @click="askMindMate"
              >
                <MessageCircle class="h-4 w-4" />
                {{ t('showcase.detail.askMindmate') }}
              </button>
              <button
                v-if="showExpertRecommend"
                type="button"
                :class="[
                  'inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors',
                  post.is_expert_recommended
                    ? 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                    : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50',
                ]"
                @click="toggleRecommend"
              >
                <Award class="h-4 w-4" />
                {{ post.is_expert_recommended ? t('showcase.detail.unrecommend') : t('showcase.detail.recommend') }}
              </button>
              <button
                v-if="showDeleteButton"
                type="button"
                class="detail-delete-btn flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-medium text-red-600"
                @click="remove"
              >
                <Trash2 class="h-4 w-4" />
                {{ t('showcase.detail.delete') }}
              </button>
            </div>

            <div
              v-if="showAuthorManageBar"
              class="flex flex-wrap gap-2 border-b border-gray-100 px-5 py-3"
            >
              <button
                v-if="showAuthorResubmit"
                type="button"
                class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
                @click="openResubmit"
              >
                <PenLine class="h-4 w-4" />
                {{ t('showcase.detail.resubmit') }}
              </button>
              <button
                v-if="showAuthorWithdraw"
                type="button"
                class="inline-flex items-center justify-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-700 hover:bg-amber-100"
                @click="withdrawCase"
              >
                <Undo2 class="h-4 w-4" />
                {{ t('showcase.detail.withdraw') }}
              </button>
              <button
                v-if="showAuthorDelist"
                type="button"
                class="inline-flex items-center justify-center gap-1.5 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-100"
                @click="delistCase"
              >
                <Trash2 class="h-4 w-4" />
                {{ t('showcase.detail.delist') }}
              </button>
            </div>

            <div class="flex border-b border-gray-100">
              <button
                v-for="tab in TEACHING_TABS"
                :key="tab"
                type="button"
                class="detail-tab flex-1 px-2 py-3 text-xs font-medium"
                :class="teachingTab === tab ? 'detail-tab--active' : 'detail-tab--idle'"
                @click="teachingTab = tab"
              >
                {{ teachingTabLabel(tab) }}
              </button>
            </div>

            <div class="flex min-h-0 flex-1 flex-col">
              <div class="flex-1 overflow-y-auto px-5 py-4">
                <p
                  v-if="teachingTab === 'intro' && introText"
                  class="whitespace-pre-line text-sm leading-relaxed text-gray-700"
                >
                  {{ introText }}
                </p>
                <ol
                  v-else-if="teachingTab === 'highlights' && highlightsList.length > 0"
                  class="list-decimal space-y-3 pl-4 text-sm leading-relaxed text-gray-700"
                >
                  <li v-for="(item, index) in highlightsList" :key="index">{{ item }}</li>
                </ol>
                <template v-else-if="teachingTab === 'reflection'">
                  <p
                    v-if="reflectionText"
                    class="whitespace-pre-line text-sm leading-relaxed text-gray-700"
                  >
                    {{ reflectionText }}
                  </p>
                  <p
                    v-else
                    class="text-sm text-gray-400"
                  >
                    {{ t('showcase.detail.emptySection') }}
                  </p>
                </template>
                <p v-else class="text-sm text-gray-400">{{ t('showcase.detail.emptySection') }}</p>

                <div v-if="showReviewActions" class="mt-6 space-y-2 border-t border-gray-100 pt-4">
                  <div class="flex gap-2">
                    <button
                      type="button"
                      class="flex-1 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
                      @click="approve"
                    >
                      {{ t('showcase.detail.approve') }}
                    </button>
                    <button
                      type="button"
                      class="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
                      @click="showRejectInput = !showRejectInput"
                    >
                      {{ t('showcase.detail.reject') }}
                    </button>
                  </div>
                  <div v-if="showRejectInput" class="flex gap-2">
                    <input
                      v-model="rejectReason"
                      type="text"
                      :placeholder="String(t('showcase.detail.reject'))"
                      class="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm outline-none focus:border-gray-400 focus:ring-2 focus:ring-gray-900/10"
                    />
                    <button
                      type="button"
                      class="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-100"
                      @click="reject"
                    >
                      {{ t('showcase.detail.reject') }}
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="displayTags.length > 0" class="border-t border-gray-100 px-5 py-3">
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="tag in displayTags"
                    :key="tag"
                    class="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1 text-xs text-gray-600"
                  >
                    <Tag class="h-3 w-3 text-gray-400" />
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 图示案例 / 模板 -->
        <template v-else>
          <div class="flex w-[60%] min-w-0 flex-col border-r border-gray-100 bg-gray-50">
            <div
              :class="[
                'relative flex shrink-0 items-center justify-between px-6 py-3',
                diagramTheme.headerGradient,
              ]"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    diagramTheme.caseTypeTagClass,
                  ]"
                >
                  {{ caseTypeEmoji(post.case_type) }}{{ caseTypeLabel(post.case_type) }}
                </span>
                <span
                  v-if="post.subject"
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    diagramTheme.subjectTagClass,
                  ]"
                >
                  {{ post.subject }}
                </span>
                <span
                  v-if="post.grade"
                  :class="[
                    'rounded-full px-3 py-0.5 text-[11px] font-semibold shadow-sm',
                    diagramTheme.gradeTagClass,
                  ]"
                >
                  {{ post.grade }}
                </span>
              </div>
              <div class="flex items-center gap-3">
                <span class="flex items-center gap-1 text-[11px] text-white/80">
                  <Eye class="h-3 w-3" />
                  {{ post.views_count }}
                </span>
              </div>
            </div>

            <div class="flex min-h-0 flex-1 flex-col overflow-hidden bg-white">
              <ShowcaseDiagramPreview
                :post-id="post.id"
                :thumbnail-url="post.thumbnail_url"
                :source-file-url="post.source_file_url"
                :spec-json-url="post.spec_json_url"
                :spec="diagramPostSpec"
                :diagram-type="post.diagram_type"
                :gallery-items="post.gallery_items"
                :watermark-name="post.author.name"
                :watermark-organization="post.author.organization"
              />
            </div>

            <div class="shrink-0 border-t border-gray-100 bg-white px-6 py-3">
              <div class="flex items-center">
                <div class="flex h-9 w-9 items-center justify-center rounded-full bg-gray-100 text-base">
                  {{ post.author.avatar ?? '👤' }}
                </div>
                <span class="ml-2 text-sm font-medium text-gray-900">{{ post.author.name }}</span>
                <span v-if="post.author.organization" class="ml-1 text-[11px] font-normal text-gray-400">
                  · {{ post.author.organization }}
                </span>
                <span class="ml-auto text-[11px] text-gray-400">{{ formatDate(post.created_at) }}</span>
              </div>
            </div>
          </div>

          <div class="flex w-[40%] min-w-0 flex-col">
            <div class="border-b border-gray-100 px-5 py-4">
              <div class="flex items-start justify-between gap-3">
                <h2 class="line-clamp-2 text-base font-bold leading-snug text-gray-900">
                  {{ post.title }}
                </h2>
                <button type="button" class="detail-modal-close shrink-0" @click="close">
                  <X class="h-5 w-5" />
                </button>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <button
                  v-if="showPublicInteractions"
                  type="button"
                  :class="[
                    'detail-like-btn inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
                    post.is_liked
                      ? 'bg-red-500 text-white shadow-sm hover:bg-red-600'
                      : 'bg-gray-100 text-gray-700 hover:bg-red-50 hover:text-red-600',
                  ]"
                  @click="toggleLike"
                >
                  <Heart class="h-4 w-4" :class="post.is_liked ? 'fill-current' : ''" />
                  {{ post.is_liked ? t('showcase.detail.liked') : t('showcase.detail.like') }}
                  <span :class="post.is_liked ? 'text-red-100' : 'font-normal text-gray-400'">
                    {{ post.likes_count }}
                  </span>
                </button>
                <button
                  v-if="showPublicInteractions"
                  type="button"
                  :class="[
                    'detail-like-btn inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors',
                    post.is_favorited
                      ? 'bg-amber-500 text-white shadow-sm hover:bg-amber-600'
                      : 'bg-gray-100 text-gray-700 hover:bg-amber-50 hover:text-amber-600',
                  ]"
                  @click="toggleFavorite"
                >
                  <Star class="h-4 w-4" :class="post.is_favorited ? 'fill-current' : ''" />
                  {{ post.is_favorited ? t('showcase.detail.favorited') : t('showcase.detail.favorite') }}
                </button>
                <span
                  v-if="post.is_expert_recommended"
                  class="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-600"
                >
                  <Award class="h-3.5 w-3.5" />
                  {{ t('showcase.expertBadge') }}
                </span>
                <span class="inline-flex items-center gap-1 text-xs text-gray-400">
                  <Eye class="h-3.5 w-3.5" />
                  {{ t('showcase.detail.views', { n: post.views_count }) }}
                </span>
              </div>
            </div>

            <div class="flex gap-2 border-b border-gray-100 px-5 py-2.5">
              <button
                v-if="diagramAction"
                type="button"
                class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-3 py-2 text-xs font-medium text-white hover:bg-gray-800 disabled:opacity-50"
                :disabled="isImporting"
                @click="runDiagramAction"
              >
                <component :is="diagramActionIcon" class="h-3.5 w-3.5" />
                {{ diagramActionLabel }}
              </button>
              <button
                v-if="showExpertRecommend"
                type="button"
                :class="[
                  'inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors',
                  post.is_expert_recommended
                    ? 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                    : 'border border-gray-200 bg-white text-gray-600 hover:bg-gray-50',
                ]"
                @click="toggleRecommend"
              >
                <Award class="h-3.5 w-3.5" />
                {{ post.is_expert_recommended ? t('showcase.detail.unrecommend') : t('showcase.detail.recommend') }}
              </button>
              <button
                v-if="showDeleteButton"
                type="button"
                class="flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-100"
                @click="remove"
              >
                <Trash2 class="h-3.5 w-3.5" />
                {{ t('showcase.detail.delete') }}
              </button>
            </div>

            <div
              v-if="showAuthorManageBar"
              class="flex flex-wrap gap-2 border-b border-gray-100 px-5 py-2.5"
            >
              <button
                v-if="showAuthorResubmit"
                type="button"
                class="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-gray-900 px-3 py-2 text-xs font-medium text-white hover:bg-gray-800"
                @click="openResubmit"
              >
                <PenLine class="h-3.5 w-3.5" />
                {{ t('showcase.detail.resubmit') }}
              </button>
              <button
                v-if="showAuthorWithdraw"
                type="button"
                class="inline-flex items-center justify-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 hover:bg-amber-100"
                @click="withdrawCase"
              >
                <Undo2 class="h-3.5 w-3.5" />
                {{ t('showcase.detail.withdraw') }}
              </button>
              <button
                v-if="showAuthorDelist"
                type="button"
                class="inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-100"
                @click="delistCase"
              >
                <Trash2 class="h-3.5 w-3.5" />
                {{ t('showcase.detail.delist') }}
              </button>
            </div>

            <div class="flex border-b border-gray-100">
              <button
                v-for="tab in DIAGRAM_TABS"
                :key="tab"
                type="button"
                class="detail-tab flex-1 px-2 py-3 text-xs font-medium"
                :class="diagramTab === tab ? 'detail-tab--active' : 'detail-tab--idle'"
                @click="diagramTab = tab"
              >
                {{ diagramTabLabel(tab) }}
              </button>
            </div>

            <div class="flex min-h-0 flex-1 flex-col">
              <div class="flex-1 overflow-y-auto px-5 py-4">
                <p
                  v-if="diagramTab === 'intro' && diagramIntroText"
                  class="whitespace-pre-line text-sm leading-relaxed text-gray-600"
                >
                  {{ diagramIntroText }}
                </p>
                <p
                  v-else-if="diagramTab === 'classroomApp' && classroomAppText"
                  class="whitespace-pre-line text-sm leading-relaxed text-gray-600"
                >
                  {{ classroomAppText }}
                </p>
                <p v-else class="text-sm text-gray-400">{{ t('showcase.detail.emptySection') }}</p>

                <div v-if="showReviewActions" class="mt-6 space-y-2 border-t border-gray-100 pt-4">
                  <div class="flex gap-2">
                    <button
                      type="button"
                      class="flex-1 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
                      @click="approve"
                    >
                      {{ t('showcase.detail.approve') }}
                    </button>
                    <button
                      type="button"
                      class="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
                      @click="showRejectInput = !showRejectInput"
                    >
                      {{ t('showcase.detail.reject') }}
                    </button>
                  </div>
                  <div v-if="showRejectInput" class="flex gap-2">
                    <input
                      v-model="rejectReason"
                      type="text"
                      :placeholder="String(t('showcase.detail.reject'))"
                      class="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm outline-none focus:border-gray-400 focus:ring-2 focus:ring-gray-900/10"
                    />
                    <button
                      type="button"
                      class="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 hover:bg-red-100"
                      @click="reject"
                    >
                      {{ t('showcase.detail.reject') }}
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="displayTags.length > 0" class="border-t border-gray-100 px-5 py-3">
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="tag in displayTags"
                    :key="tag"
                    class="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1 text-xs text-gray-600"
                  >
                    <Tag class="h-3 w-3 text-gray-400" />
                    {{ tag }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </template>
        </div>
      </div>
      <div v-else-if="isLoading" class="rounded-2xl bg-white px-8 py-12 text-sm text-gray-400 shadow-2xl">
        …
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.detail-modal-close {
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

.detail-modal-close:hover {
  background: #f3f4f6;
  color: #4b5563;
}

.detail-modal-close:focus,
.detail-modal-close:focus-visible {
  outline: none;
  box-shadow: none;
}

.detail-header-stat-btn {
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
  padding: 0;
}

.detail-header-stat-btn:focus,
.detail-header-stat-btn:focus-visible {
  outline: none;
  box-shadow: none;
}

.detail-like-btn {
  border: none;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.detail-like-btn:focus,
.detail-like-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgb(239 68 68 / 0.35);
}

.detail-mindmate-btn,
.detail-delete-btn,
.detail-tab {
  border: none;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.detail-delete-btn {
  border: 1px solid #fecaca;
  background: #fff;
}

.detail-delete-btn:focus,
.detail-delete-btn:focus-visible,
.detail-mindmate-btn:focus,
.detail-mindmate-btn:focus-visible {
  outline: none;
}

.detail-tab--active {
  border-bottom: 2px solid #111827;
  color: #111827;
}

.detail-tab--idle {
  border-bottom: 2px solid transparent;
  color: #9ca3af;
}

.detail-tab--idle:hover {
  color: #4b5563;
}
</style>
