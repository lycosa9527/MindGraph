<script setup lang="ts">
/**
 * Teacher review / student view modal for a class-wall submission.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Loader2, Maximize2, Minimize2, Pin, Star, ThumbsUp, X } from '@lucide/vue'

import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useRouter } from 'vue-router'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import {
  fetchSubmissionPreview,
  type LearningSubmission,
} from '@/utils/learningSpaceApi'

export interface ReviewDraft {
  scores: Record<string, number>
  comment: string
  liked: boolean
  pinned: boolean
}

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  submission: LearningSubmission | null
  dimensions: string[]
  assignmentTitle: string
  /** Teacher edits rubric; student/classmates view + save to library. */
  mode?: 'edit' | 'view'
  initialDraft?: ReviewDraft | null
}>()

const emit = defineEmits<{
  save: [payload: { submissionId: number; draft: ReviewDraft }]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const savedDiagramsStore = useSavedDiagramsStore()

const draft = reactive<ReviewDraft>({
  scores: {},
  comment: '',
  liked: false,
  pinned: false,
})

const previewSpec = ref<Record<string, unknown> | null>(null)
const previewLoading = ref(false)
const savingLibrary = ref(false)
const previewFullscreen = ref(false)
const previewMeta = ref<{ title: string; diagramType: string }>({
  title: '',
  diagramType: 'mind_map',
})

const isView = computed(() => props.mode === 'view')

const dims = computed(() =>
  props.dimensions.length
    ? props.dimensions
    : [
        t('learningSpace.eval.infoExtract'),
        t('learningSpace.eval.classify'),
        t('learningSpace.eval.compare'),
        t('learningSpace.eval.causeEffect'),
      ]
)

function emptyScores(): Record<string, number> {
  return Object.fromEntries(dims.value.map((d) => [d, 0]))
}

function draftFromSubmission(sub: LearningSubmission | null): ReviewDraft {
  if (!sub) {
    return { scores: emptyScores(), comment: '', liked: false, pinned: false }
  }
  return {
    scores: { ...emptyScores(), ...(sub.review_scores ?? {}) },
    comment: sub.review_comment ?? '',
    liked: Boolean(sub.review_liked),
    pinned: Boolean(sub.review_pinned),
  }
}

function applyDraft(source: ReviewDraft | null | undefined): void {
  draft.scores = { ...emptyScores(), ...(source?.scores ?? {}) }
  draft.comment = source?.comment ?? ''
  draft.liked = source?.liked ?? false
  draft.pinned = source?.pinned ?? false
}

const hasTeacherReview = computed(
  () =>
    Boolean(props.submission?.reviewed_at) ||
    Boolean(props.submission?.review_comment) ||
    Boolean(props.submission?.review_scores && Object.keys(props.submission.review_scores).length)
)

async function loadPreview(submissionId: number): Promise<void> {
  previewLoading.value = true
  previewSpec.value = null
  try {
    const detail = await fetchSubmissionPreview(submissionId)
    previewSpec.value = detail.preview_spec ?? null
    previewMeta.value = {
      title: detail.preview_title || detail.assignment_title || props.assignmentTitle,
      diagramType: detail.preview_diagram_type || 'mind_map',
    }
    if (isView.value) {
      applyDraft(draftFromSubmission(detail))
    }
  } catch {
    previewSpec.value = null
  } finally {
    previewLoading.value = false
  }
}

watch(
  () => [visible.value, props.submission?.id, props.mode] as const,
  ([open]) => {
    if (!open || !props.submission) return
    previewFullscreen.value = false
    if (isView.value) {
      applyDraft(draftFromSubmission(props.submission))
    } else {
      applyDraft(props.initialDraft ?? draftFromSubmission(props.submission))
    }
    void loadPreview(props.submission.id)
  }
)

function setStar(dim: string, n: number): void {
  if (isView.value) return
  draft.scores[dim] = draft.scores[dim] === n ? 0 : n
}

function onClose(): void {
  previewFullscreen.value = false
  visible.value = false
}

function togglePreviewFullscreen(): void {
  previewFullscreen.value = !previewFullscreen.value
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && previewFullscreen.value) {
    event.stopPropagation()
    previewFullscreen.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown, true)
})

function onSave(): void {
  if (!props.submission || isView.value) return
  emit('save', {
    submissionId: props.submission.id,
    draft: {
      scores: { ...draft.scores },
      comment: draft.comment,
      liked: draft.liked,
      pinned: draft.pinned,
    },
  })
}

async function onSaveToLibrary(): Promise<void> {
  if (!props.submission) return
  const spec = previewSpec.value
  if (!spec) {
    notify.error(t('learningSpace.noPreview'))
    return
  }
  savingLibrary.value = true
  try {
    const title =
      previewMeta.value.title ||
      props.submission.assignment_title ||
      props.assignmentTitle ||
      t('learningSpace.tabClassWall')
    const saved = await savedDiagramsStore.saveDiagram(
      title,
      previewMeta.value.diagramType || 'mind_map',
      spec,
      'zh',
      props.submission.diagram_thumbnail ?? null
    )
    if (!saved) {
      notify.error(savedDiagramsStore.error || t('community.post.importFail'))
      return
    }
    savedDiagramsStore.clearActiveDiagram()
    notify.success(t('learningSpace.saveToLibraryOk'))
    visible.value = false
    await router.push({ path: '/canvas', query: { diagramId: saved.id } })
  } catch (error) {
    notify.error(error instanceof Error ? error.message : t('community.post.importFail'))
  } finally {
    savingLibrary.value = false
  }
}

const studentLabel = computed(
  () => props.submission?.student_name || String(props.submission?.student_user_id ?? '')
)

const headerTitle = computed(() =>
  props.submission?.assignment_title || props.assignmentTitle || t('learningSpace.submissionsBoard')
)
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && submission"
      class="ls-modal-overlay"
      @click.self="onClose"
    >
      <div
        class="ls-modal ls-modal--review"
        :class="{ 'ls-modal--review-fs': previewFullscreen }"
        role="dialog"
        aria-modal="true"
      >
        <header class="ls-modal__head">
          <div class="ls-modal__head-text">
            <p class="ls-modal__eyebrow">{{ headerTitle }}</p>
            <h2 class="ls-modal__title">{{ studentLabel }}</h2>
          </div>
          <button
            type="button"
            class="ls-modal__close"
            :aria-label="t('common.close')"
            @click="onClose"
          >
            <X :size="18" />
          </button>
        </header>

        <div
          class="ls-review"
          :class="{ 'ls-review--fs': previewFullscreen }"
        >
          <div class="ls-review__preview">
            <button
              v-if="previewSpec || submission.diagram_thumbnail"
              type="button"
              class="ls-review__fs-btn"
              :title="
                previewFullscreen
                  ? t('learningSpace.exitFullscreen')
                  : t('learningSpace.previewFullscreen')
              "
              :aria-label="
                previewFullscreen
                  ? t('learningSpace.exitFullscreen')
                  : t('learningSpace.previewFullscreen')
              "
              @click="togglePreviewFullscreen"
            >
              <Minimize2
                v-if="previewFullscreen"
                :size="16"
              />
              <Maximize2
                v-else
                :size="16"
              />
            </button>
            <div
              v-if="previewLoading"
              class="ls-review__empty"
            >
              <Loader2
                class="animate-spin"
                :size="22"
              />
            </div>
            <ShowcaseInlineDiagramPreview
              v-else-if="previewSpec"
              :spec="previewSpec"
              :thumbnail-url="submission.diagram_thumbnail"
            />
            <img
              v-else-if="submission.diagram_thumbnail"
              :src="submission.diagram_thumbnail"
              alt=""
              class="ls-review__img"
            />
            <div
              v-else
              class="ls-review__empty"
            >
              {{ t('learningSpace.noPreview') }}
            </div>
          </div>

          <div
            v-if="!previewFullscreen"
            class="ls-review__side"
          >
            <h3 class="ls-review__side-title">
              {{
                isView
                  ? t('learningSpace.teacherReview')
                  : t('learningSpace.reviewByDimension')
              }}
            </h3>

            <template v-if="!isView || hasTeacherReview">
              <div
                v-for="dim in dims"
                :key="dim"
                class="ls-review__dim"
              >
                <div class="ls-review__dim-label">{{ dim }}</div>
                <div class="ls-review__stars">
                  <button
                    v-for="n in 5"
                    :key="n"
                    type="button"
                    class="ls-review__star"
                    :class="{ 'ls-review__star--on': (draft.scores[dim] || 0) >= n }"
                    :disabled="isView"
                    @click="setStar(dim, n)"
                  >
                    <Star :size="18" />
                  </button>
                </div>
              </div>

              <label
                v-if="!isView"
                class="ls-field"
              >
                {{ t('learningSpace.reviewComment') }}
                <textarea
                  v-model="draft.comment"
                  rows="4"
                  :placeholder="t('learningSpace.reviewCommentHint')"
                />
              </label>
              <p
                v-else-if="draft.comment"
                class="ls-muted"
                style="white-space: pre-wrap"
              >
                {{ draft.comment }}
              </p>
              <p
                v-else-if="isView"
                class="ls-muted"
              >
                {{ t('learningSpace.noTeacherComment') }}
              </p>

              <div
                v-if="!isView"
                class="ls-review__actions"
              >
                <button
                  type="button"
                  class="ls-chip"
                  :class="{ 'ls-chip--on': draft.liked }"
                  @click="draft.liked = !draft.liked"
                >
                  <ThumbsUp :size="14" />
                  {{ t('learningSpace.reviewLike') }}
                </button>
                <button
                  type="button"
                  class="ls-chip"
                  :class="{ 'ls-chip--on': draft.pinned }"
                  @click="draft.pinned = !draft.pinned"
                >
                  <Pin :size="14" />
                  {{ t('learningSpace.reviewPin') }}
                </button>
              </div>
              <div
                v-else-if="draft.liked || draft.pinned"
                class="ls-review__actions"
              >
                <span
                  v-if="draft.liked"
                  class="ls-chip ls-chip--on"
                >
                  <ThumbsUp :size="14" />
                  {{ t('learningSpace.reviewLike') }}
                </span>
                <span
                  v-if="draft.pinned"
                  class="ls-chip ls-chip--on"
                >
                  <Pin :size="14" />
                  {{ t('learningSpace.reviewPin') }}
                </span>
              </div>
            </template>
            <p
              v-else
              class="ls-muted"
            >
              {{ t('learningSpace.waitingTeacherReview') }}
            </p>
          </div>
        </div>

        <footer
          v-if="(isView && !previewFullscreen) || (!isView && !previewFullscreen)"
          class="ls-modal__foot"
          :class="{ 'ls-modal__foot--end': true }"
        >
          <button
            v-if="isView"
            type="button"
            class="ls-btn ls-btn--primary"
            :disabled="savingLibrary || previewLoading || !previewSpec"
            @click="onSaveToLibrary"
          >
            <Loader2
              v-if="savingLibrary"
              class="animate-spin"
              :size="16"
            />
            {{ t('learningSpace.saveToLibrary') }}
          </button>
          <button
            v-else
            type="button"
            class="ls-btn ls-btn--primary"
            @click="onSave"
          >
            {{ t('learningSpace.reviewSubmit') }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
