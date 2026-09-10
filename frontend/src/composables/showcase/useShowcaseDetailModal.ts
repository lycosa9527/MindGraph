/**
 * Showcase case detail modal state and handlers.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { Download, LayoutTemplate, PenLine } from '@lucide/vue'

import {
  type ShowcaseCaseType,
  caseTypeEmoji,
  caseTypeTheme,
} from '@/components/showcase/showcaseShared'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { eventBus } from '@/composables/core/useEventBus'
import {
  postCanDelist,
  postCanResubmit,
  postCanWithdraw,
} from '@/composables/showcase/showcaseAuthorManage'
import { useShowcaseDiagramAction } from '@/composables/showcase/useShowcaseDiagramAction'
import { useAuthStore, useShowcaseStore } from '@/stores'
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

function teachingDocNeedsPreview(post: ShowcasePost): boolean {
  if (post.case_type !== 'teaching_design' || post.preview_url) return false
  const path = (post.attachment_url || '').toLowerCase().split('?')[0] || ''
  return path.endsWith('.pptx') || path.endsWith('.docx') || path.endsWith('.doc')
}

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

export type ShowcaseDetailModalProps = {
  visible: boolean
  postId: string | null
  postPreview?: ShowcasePost | null
  mode?: 'public' | 'admin'
  publishedManage?: boolean
}

export type ShowcaseDetailModalEmit = {
  (e: 'update:visible', value: boolean): void
  (e: 'updated', post: ShowcasePost): void
  (e: 'deleted'): void
  (e: 'edit', postId: string): void
}

export function useShowcaseDetailModal(
  props: ShowcaseDetailModalProps,
  emit: ShowcaseDetailModalEmit
) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const authStore = useAuthStore()
  const { can: adminCan } = useAdminAccess()
  const router = useRouter()
  const { actionLabel, resolveActionForPost, handleDiagramAction, isImporting } =
    useShowcaseDiagramAction()

  const post = ref<ShowcasePost | null>(null)
  const diagramPreviewRef = ref<{
    getActiveDiagramSpec?: () => Record<string, unknown> | null
  } | null>(null)
  const isLoading = ref(false)
  const isActionBusy = ref(false)
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
    if (!isAdminMode.value || props.publishedManage || post.value?.status !== 'pending')
      return false
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

  let loadPostToken = 0

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

  const offCoverReady = eventBus.on(
    'showcase:cover_ready',
    ({ postId, thumbnailUrl, previewUrl }) => {
      if (!props.visible || !post.value || post.value.id !== postId) return
      // Patch URLs from SSE only. Do not reload the post on thumb-only ready —
      // that re-enqueues + reopens cover-stream in a loop while preview_path is missing.
      post.value = {
        ...post.value,
        ...(thumbnailUrl ? { thumbnail_url: thumbnailUrl } : {}),
        ...(previewUrl ? { preview_url: previewUrl } : {}),
      }
    }
  )

  onUnmounted(() => {
    offCoverReady()
    loadPostToken += 1
  })

  async function loadPost() {
    const requestId = props.postId
    if (!requestId) return
    const token = ++loadPostToken
    isLoading.value = true
    loadError.value = null
    try {
      const loaded = await getShowcasePost(requestId)
      if (token !== loadPostToken || props.postId !== requestId) return
      post.value = loaded
      // get_post enqueues missing LO preview; open SSE so the reader updates live.
      if (loaded && teachingDocNeedsPreview(loaded)) {
        useShowcaseStore().markCoverPending(loaded.id)
      }
    } catch (e) {
      if (token !== loadPostToken || props.postId !== requestId) return
      const msg = e instanceof Error ? e.message : String(t('showcase.detail.loadFailed'))
      if (!props.postPreview) {
        loadError.value = msg
        notify.error(msg)
      }
      if (!post.value && props.postPreview) {
        post.value = props.postPreview
      }
    } finally {
      if (token === loadPostToken) {
        isLoading.value = false
      }
    }
  }

  async function toggleLike() {
    if (!post.value || isActionBusy.value) return
    isActionBusy.value = true
    try {
      const res = await toggleShowcasePostLike(post.value.id)
      post.value = { ...post.value, is_liked: res.liked, likes_count: res.likes_count }
      emit('updated', post.value)
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function toggleFavorite() {
    if (!post.value || post.value.status !== 'approved' || isActionBusy.value) return
    isActionBusy.value = true
    try {
      const res = await toggleShowcasePostFavorite(post.value.id)
      post.value = { ...post.value, is_favorited: res.favorited }
      emit('updated', post.value)
      notify.success(
        String(res.favorited ? t('showcase.detail.favorited') : t('showcase.detail.unfavorited')),
        2000
      )
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function toggleRecommend() {
    if (!post.value || isActionBusy.value) return
    isActionBusy.value = true
    try {
      const res = await toggleShowcaseExpertRecommend(post.value.id)
      post.value = res.post
      emit('updated', post.value)
      notify.success(
        String(
          res.is_expert_recommended
            ? t('showcase.detail.recommendedOn')
            : t('showcase.detail.recommendedOff')
        ),
        2000
      )
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function approve() {
    const postId = (props.postId ?? post.value?.id ?? '').trim()
    if (!postId || isActionBusy.value) return
    isActionBusy.value = true
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
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function reject() {
    const postId = (props.postId ?? post.value?.id ?? '').trim()
    if (!postId || isActionBusy.value) return
    isActionBusy.value = true
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
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function confirmAuthorAction(titleKey: string, messageKey: string): Promise<boolean> {
    const title = post.value?.title?.trim() || post.value?.id || ''
    try {
      await swissGlassConfirm(String(t(messageKey, { title })), String(t(titleKey)), {
        confirmButtonText: String(t('showcase.detail.confirm')),
        cancelButtonText: String(t('showcase.detail.cancel')),
        type: 'warning',
      })
      return true
    } catch {
      return false
    }
  }

  async function withdrawCase() {
    const postId = (props.postId ?? post.value?.id ?? '').trim()
    if (!postId || isActionBusy.value) return
    if (
      !(await confirmAuthorAction(
        'showcase.detail.withdrawTitle',
        'showcase.detail.withdrawConfirm'
      ))
    ) {
      return
    }
    isActionBusy.value = true
    try {
      await withdrawShowcasePost(postId)
      notify.success(t('showcase.withdrawn'))
      emit('deleted')
      emit('update:visible', false)
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function delistCase() {
    const postId = (props.postId ?? post.value?.id ?? '').trim()
    if (!postId || isActionBusy.value) return
    if (
      !(await confirmAuthorAction('showcase.detail.delistTitle', 'showcase.detail.delistConfirm'))
    ) {
      return
    }
    isActionBusy.value = true
    try {
      const res = await delistShowcasePost(postId)
      notify.success(t('showcase.delisted'))
      post.value = res.post
      emit('updated', res.post)
      emit('update:visible', false)
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
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
    if (isActionBusy.value) return
    if (props.publishedManage) {
      const title = post.value?.title?.trim() || postId
      try {
        await swissGlassConfirm(
          String(t('admin.showcase.published.deleteConfirm', { title })),
          String(t('admin.showcase.published.deleteTitle')),
          {
            confirmButtonText: String(t('admin.delete')),
            cancelButtonText: String(t('admin.cancel')),
            type: 'warning',
          }
        )
      } catch {
        return
      }
    }
    isActionBusy.value = true
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
      notify.error(e instanceof Error ? e.message : String(t('showcase.detail.actionFailed')))
    } finally {
      isActionBusy.value = false
    }
  }

  async function runDiagramAction() {
    if (!post.value) return
    const activeSpec = diagramPreviewRef.value?.getActiveDiagramSpec?.() ?? null
    await handleDiagramAction(post.value, activeSpec ?? diagramPostSpec.value, {
      closeModal: close,
    })
  }

  function askMindMate() {
    if (!post.value) return
    // MindMate loads the case as a pending Dify attachment; user types their own question.
    void router.push({
      name: 'MindMate',
      query: { showcase_post: post.value.id },
    })
    close()
  }

  function close() {
    emit('update:visible', false)
  }

  return {
    post,
    diagramPreviewRef,
    isLoading,
    isActionBusy,
    loadError,
    rejectReason,
    showRejectInput,
    teachingTab,
    diagramTab,
    TEACHING_TABS,
    DIAGRAM_TABS,
    isTeachingDesign,
    diagramAction,
    diagramActionLabel,
    diagramActionIcon,
    teachingTheme,
    diagramTheme,
    teachingSpec,
    diagramPostSpec,
    introText,
    diagramIntroText,
    classroomAppText,
    highlightsList,
    docFallbackText,
    reflectionText,
    displayTags,
    isAdminMode,
    isOwnPost,
    showPublicInteractions,
    showAuthorWithdraw,
    showAuthorDelist,
    showAuthorResubmit,
    showAuthorManageBar,
    showPlatformDelete,
    showDeleteButton,
    showExpertRecommend,
    showReviewActions,
    caseTypeLabel,
    teachingTabLabel,
    diagramTabLabel,
    formatDate,
    toggleLike,
    toggleFavorite,
    toggleRecommend,
    approve,
    reject,
    withdrawCase,
    delistCase,
    openResubmit,
    remove,
    runDiagramAction,
    askMindMate,
    close,
    isImporting,
    t,
    caseTypeEmoji,
  }
}
