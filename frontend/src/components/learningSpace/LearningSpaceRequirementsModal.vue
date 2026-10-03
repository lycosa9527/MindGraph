<script setup lang="ts">
/**
 * Full assignment brief — instructions, images, template (.mg) preview.
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ExternalLink, Loader2, X } from '@lucide/vue'

import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import {
  type LsReferenceDiagram,
  assignmentHasTeacherTemplate,
  assignmentHasWorkingDiagram,
  assignmentIsClosed,
  assignmentReferenceDiagrams,
  assignmentTemplateRole,
  diagramTypeLabelKey,
  formatLsDateTime,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { apiGet } from '@/utils/apiClient'
import {
  type LearningAssignment,
  type LearningTemplatePreview,
  fetchAssignmentTemplatePreview,
  fetchReferenceDiagramPreview,
} from '@/utils/learningSpaceApi'

const AI_TOOL_KEYS = [
  'topic_generate',
  'file_generate',
  'web_generate',
  'voice_summary',
  'ai_brainstorm',
  'conversational_edit',
  'node_subgraph',
  'node_explain',
  'mind_classroom',
] as const

const EVAL_PRESET_KEYS: Record<string, string> = {
  信息提取: 'learningSpace.eval.infoExtract',
  分类整理: 'learningSpace.eval.classify',
  比较分析: 'learningSpace.eval.compare',
  因果分析: 'learningSpace.eval.causeEffect',
  问题解决: 'learningSpace.eval.problemSolve',
  发散思考: 'learningSpace.eval.diverge',
  评价判断: 'learningSpace.eval.evaluate',
  创新表达: 'learningSpace.eval.innovate',
}

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  assignment: LearningAssignment | null
  className: string
  /** Teacher admin brief vs student-facing brief. */
  audience?: 'teacher' | 'student'
}>()

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()

const templatePreview = ref<LearningTemplatePreview | null>(null)
const templateLoading = ref(false)
const openingCanvas = ref(false)
const lightboxSrc = ref<string | null>(null)
const diagramLightbox = ref<{
  spec: Record<string, unknown> | null
  thumbnail: string | null
} | null>(null)
const instructionPreviewUrls = ref<Record<number, string>>({})

const isStudentAudience = computed(() => props.audience === 'student')

const perms = computed(() => (props.assignment?.ai_permissions ?? {}) as Record<string, unknown>)

const enabledTools = computed(() =>
  AI_TOOL_KEYS.filter((key) => Boolean(perms.value[key])).map((key) => t(aiToolLabelKey(key)))
)

const evalDims = computed(() => {
  const dims = perms.value.evaluation_dimensions
  if (!Array.isArray(dims)) return []
  return dims.map((d) => String(d).trim()).filter(Boolean)
})

const isTeacherOwner = computed(() => {
  const a = props.assignment
  if (!a || !authStore.user?.id) return false
  return Number(a.created_by) === Number(authStore.user.id)
})

const diagramTypeLabel = computed(() =>
  t(diagramTypeLabelKey(props.assignment?.ai_permissions?.diagram_type))
)

const hasWorkingDiagram = computed(() => assignmentHasWorkingDiagram(props.assignment))

const hasTeacherTemplate = computed(() =>
  assignmentHasTeacherTemplate(props.assignment, templatePreview.value?.preview_spec)
)

const templateRole = computed(() => assignmentTemplateRole(props.assignment))

const workingPreviewSpec = computed(() => templatePreview.value?.preview_spec ?? null)

const workingPreviewThumbnail = computed(() => {
  const a = props.assignment
  return templatePreview.value?.thumbnail || a?.template_thumbnail || null
})

const showStudentTemplate = computed(
  () => hasWorkingDiagram.value && (hasTeacherTemplate.value || templateLoading.value)
)

const showStudentMaterials = computed(
  () =>
    hasInstructionImages.value || showStudentTemplate.value || referenceDiagrams.value.length > 0
)

const hasInstructionImages = computed(() => (props.assignment?.instruction_images ?? []).length > 0)

const referenceDiagrams = computed(() => assignmentReferenceDiagrams(props.assignment))

const showTeacherAttachments = computed(
  () => hasWorkingDiagram.value || referenceDiagrams.value.length > 0 || hasInstructionImages.value
)

function aiToolLabelKey(key: (typeof AI_TOOL_KEYS)[number]): string {
  return `learningSpace.aiTool.${key}`
}

function instructionImageApiPath(index: number): string {
  const assignmentId = props.assignment?.id
  if (assignmentId == null || index < 0) return ''
  return `/api/learning-space/instruction-images/${assignmentId}/${index}?proxy=1`
}

function revokeInstructionPreviews(): void {
  for (const url of Object.values(instructionPreviewUrls.value)) {
    URL.revokeObjectURL(url)
  }
  instructionPreviewUrls.value = {}
}

async function loadInstructionPreviews(): Promise<void> {
  revokeInstructionPreviews()
  const items = props.assignment?.instruction_images ?? []
  if (!props.assignment?.id || !items.length) return
  await Promise.all(
    items.map(async (_src, idx) => {
      const path = instructionImageApiPath(idx)
      if (!path) return
      try {
        const response = await apiGet(path)
        if (!response.ok) return
        const blob = await response.blob()
        if (!blob.size) return
        instructionPreviewUrls.value = {
          ...instructionPreviewUrls.value,
          [idx]: URL.createObjectURL(blob),
        }
      } catch {
        /* credentialed fetch failed — img fallback uses instructionImageApiPath */
      }
    })
  )
}

function instructionDisplaySrc(idx: number): string {
  return instructionPreviewUrls.value[idx] ?? instructionImageApiPath(idx)
}

function openInstructionLightbox(idx: number): void {
  const src = instructionDisplaySrc(idx)
  if (!src.trim()) return
  lightboxSrc.value = src
}

function dimLabel(dim: string): string {
  const key = EVAL_PRESET_KEYS[dim]
  return key ? t(key) : dim
}

const modalTitle = computed(() =>
  isStudentAudience.value ? t('learningSpace.studentReqTitle') : t('learningSpace.viewRequirements')
)

const statusText = computed(() => {
  const a = props.assignment
  if (!a) return ''
  if (a.status === 'draft') return t('learningSpace.filterDraft')
  if (assignmentIsClosed(a)) {
    return isStudentAudience.value
      ? t('learningSpace.studentReqStatusClosed')
      : t('learningSpace.statusClosed')
  }
  return isStudentAudience.value
    ? t('learningSpace.studentReqStatusActive')
    : t('learningSpace.statusActive')
})

async function loadTemplate(): Promise<void> {
  const a = props.assignment
  templatePreview.value = null
  if (!a) {
    return
  }
  if (
    hasWorkingDiagram.value &&
    !(
      isStudentAudience.value &&
      (a.ai_permissions?.template_role === 'none' ||
        a.ai_permissions?.has_teacher_template === false)
    )
  ) {
    templateLoading.value = true
    try {
      templatePreview.value = await fetchAssignmentTemplatePreview(a.id)
    } catch {
      templatePreview.value = null
    } finally {
      templateLoading.value = false
    }
  }
}

function openWorkingDiagram(): void {
  openDiagramLightbox(workingPreviewSpec.value, workingPreviewThumbnail.value)
}

async function openReferenceDiagram(item: LsReferenceDiagram): Promise<void> {
  const assignmentId = props.assignment?.id
  if (assignmentId == null) return
  try {
    const detail = await fetchReferenceDiagramPreview(assignmentId, item.id)
    openDiagramLightbox(detail.preview_spec, detail.thumbnail || item.thumbnail)
  } catch {
    if (item.thumbnail) openImageLightbox(item.thumbnail)
  }
}

watch(
  () =>
    [
      visible.value,
      props.assignment?.id,
      (props.assignment?.instruction_images ?? []).length,
    ] as const,
  ([open]) => {
    if (open && props.assignment) {
      void loadTemplate()
      void loadInstructionPreviews()
    } else if (!open) {
      revokeInstructionPreviews()
    }
  }
)

function onClose(): void {
  visible.value = false
  lightboxSrc.value = null
  diagramLightbox.value = null
  revokeInstructionPreviews()
}

function openImageLightbox(src: string): void {
  if (!src.trim()) return
  lightboxSrc.value = src
}

function closeImageLightbox(): void {
  lightboxSrc.value = null
}

function openDiagramLightbox(
  spec: Record<string, unknown> | null,
  thumbnail: string | null | undefined
): void {
  if (!spec && !thumbnail) return
  diagramLightbox.value = { spec, thumbnail: thumbnail || null }
}

function closeDiagramLightbox(): void {
  diagramLightbox.value = null
}

async function onOpenInCanvas(): Promise<void> {
  const a = props.assignment
  const preview = templatePreview.value
  if (!a || !preview) return

  if (isTeacherOwner.value && a.template_diagram_id) {
    savedDiagramsStore.clearActiveDiagram()
    visible.value = false
    await router.push({ path: '/canvas', query: { diagramId: a.template_diagram_id } })
    return
  }

  if (!preview.preview_spec) {
    notify.errorKey('learningSpace.noPreview')
    return
  }

  openingCanvas.value = true
  try {
    const saved = await savedDiagramsStore.saveDiagram(
      preview.title || a.title,
      preview.diagram_type || 'mind_map',
      preview.preview_spec,
      preview.language || 'zh',
      preview.thumbnail
    )
    if (!saved) {
      notify.error(savedDiagramsStore.error || t('community.post.importFail'))
      return
    }
    savedDiagramsStore.clearActiveDiagram()
    notify.successKey('learningSpace.saveToLibraryOk')
    visible.value = false
    await router.push({ path: '/canvas', query: { diagramId: saved.id } })
  } catch (error) {
    notify.error(error instanceof Error ? error.message : t('community.post.importFail'))
  } finally {
    openingCanvas.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible && assignment"
      class="ls-modal-overlay"
      @click.self="onClose"
    >
      <div
        class="ls-modal ls-modal--req"
        role="dialog"
        aria-modal="true"
      >
        <header class="ls-modal__head">
          <div class="ls-modal__head-text">
            <template v-if="isStudentAudience">
              <h2 class="ls-modal__title">{{ assignment.title }}</h2>
            </template>
            <template v-else>
              <p class="ls-modal__eyebrow">{{ assignment.title }}</p>
              <h2 class="ls-modal__title">{{ modalTitle }}</h2>
            </template>
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
          v-if="isStudentAudience"
          class="ls-modal__body ls-req-scroll"
        >
          <dl class="ls-req-dl ls-req-dl--compact">
            <div>
              <dt><I18nText k="learningSpace.diagramTypeLabel" /></dt>
              <dd>{{ diagramTypeLabel }}</dd>
            </div>
            <div v-if="assignment.due_at">
              <dt><I18nText k="learningSpace.due" /></dt>
              <dd>{{ formatLsDateTime(assignment.due_at) }}</dd>
            </div>
            <div>
              <dt><I18nText k="learningSpace.studentReqResubmit" /></dt>
              <dd>
                <I18nText
                  v-if="perms.allow_resubmit !== false"
                  k="learningSpace.studentReqResubmitYes"
                /><I18nText
                  v-else
                  k="learningSpace.studentReqResubmitNo"
                />
              </dd>
            </div>
          </dl>
          <p
            v-if="assignment.instructions"
            class="ls-req-body"
          >
            {{ assignment.instructions }}
          </p>
          <ul
            v-if="evalDims.length"
            class="ls-req-chips"
          >
            <li
              v-for="dim in evalDims"
              :key="dim"
            >
              {{ dimLabel(dim) }}
            </li>
          </ul>
          <ul
            v-if="perms.ai_assist && enabledTools.length"
            class="ls-req-chips"
          >
            <li
              v-for="label in enabledTools"
              :key="label"
            >
              {{ label }}
            </li>
          </ul>
          <section
            v-if="showStudentMaterials"
            class="ls-req-section"
          >
            <h3>
              <I18nText
                v-if="templateRole === 'scaffold'"
                k="learningSpace.studentReqScaffold"
              /><I18nText
                v-else
                k="learningSpace.studentReqMaterials"
              />
            </h3>
            <p class="ls-muted">
              <I18nText
                v-if="templateRole === 'scaffold'"
                k="learningSpace.studentReqScaffoldHint"
              /><I18nText
                v-else
                k="learningSpace.studentReqMaterialsHint"
              />
            </p>
            <div
              v-if="showStudentTemplate"
              class="ls-req-template"
            >
              <div
                v-if="templateLoading"
                class="ls-req-template__frame ls-req-template__loading"
              >
                <Loader2
                  class="animate-spin"
                  :size="20"
                />
              </div>
              <button
                v-else-if="hasTeacherTemplate"
                type="button"
                class="ls-req-img-btn"
                @click="openWorkingDiagram"
              >
                <img
                  v-if="workingPreviewThumbnail"
                  :src="workingPreviewThumbnail"
                  alt=""
                  class="ls-req-img"
                />
                <span
                  v-else
                  class="ls-muted"
                  ><I18nText k="learningSpace.noPreview"
                /></span>
              </button>
              <button
                v-if="hasTeacherTemplate"
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                style="margin-top: 0.65rem"
                :disabled="openingCanvas || templateLoading || !workingPreviewSpec"
                @click="onOpenInCanvas"
              >
                <ExternalLink :size="14" />
                <I18nText k="learningSpace.studentReqOpenTemplate" />
              </button>
            </div>
            <div
              v-if="hasInstructionImages || referenceDiagrams.length"
              class="ls-req-attach-list"
              style="margin-top: 0.65rem"
            >
              <article
                v-for="item in referenceDiagrams"
                :key="item.id"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">
                  <I18nText k="learningSpace.extraDiagramAsReference" />
                </p>
                <button
                  type="button"
                  class="ls-req-img-btn"
                  @click="openReferenceDiagram(item)"
                >
                  <img
                    v-if="item.thumbnail"
                    :src="item.thumbnail"
                    alt=""
                    class="ls-req-img"
                  />
                  <span
                    v-else
                    class="ls-muted"
                    >{{ item.title }}</span
                  >
                </button>
              </article>
              <article
                v-for="(src, idx) in assignment.instruction_images || []"
                :key="`img-${idx}`"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label"><I18nText k="learningSpace.instructionImage" /></p>
                <button
                  type="button"
                  class="ls-req-img-btn"
                  @click="openInstructionLightbox(idx)"
                >
                  <img
                    :src="instructionDisplaySrc(idx)"
                    alt=""
                    class="ls-req-img ls-req-img--photo"
                  />
                </button>
              </article>
            </div>
          </section>
        </div>
        <div
          v-else
          class="ls-modal__body ls-req-scroll"
        >
          <section class="ls-req-section">
            <h3><I18nText k="learningSpace.reqOverview" /></h3>
            <dl class="ls-req-dl">
              <div>
                <dt><I18nText k="learningSpace.class" /></dt>
                <dd>{{ className }}</dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.diagramTypeLabel" /></dt>
                <dd>{{ diagramTypeLabel }}</dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.status" /></dt>
                <dd>{{ statusText }}</dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.due" /></dt>
                <dd>{{ formatLsDateTime(assignment.due_at) }}</dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.publishedAt" /></dt>
                <dd>{{ formatLsDateTime(assignment.created_at) }}</dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.latePolicy" /></dt>
                <dd>
                  <I18nText
                    v-if="perms.allow_late_submit"
                    k="learningSpace.allowLateYes"
                  /><I18nText
                    v-else
                    k="learningSpace.allowLateNo"
                  />
                </dd>
              </div>
              <div>
                <dt><I18nText k="learningSpace.resubmitPolicy" /></dt>
                <dd>
                  <I18nText
                    v-if="perms.allow_resubmit !== false"
                    k="learningSpace.allowResubmitYes"
                  /><I18nText
                    v-else
                    k="learningSpace.allowResubmitNo"
                  />
                </dd>
              </div>
            </dl>
          </section>

          <section
            v-if="showTeacherAttachments"
            class="ls-req-section"
          >
            <h3><I18nText k="learningSpace.attachments" /></h3>
            <p class="ls-muted"><I18nText k="learningSpace.templateMgHint" /></p>
            <div class="ls-req-attach-list">
              <article
                v-if="hasWorkingDiagram"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">
                  <I18nText k="learningSpace.attachWorkingDiagram" />
                </p>
                <div class="ls-req-template">
                  <div
                    v-if="templateLoading"
                    class="ls-req-template__frame ls-req-template__loading"
                  >
                    <Loader2
                      class="animate-spin"
                      :size="20"
                    />
                  </div>
                  <button
                    v-else-if="workingPreviewSpec || workingPreviewThumbnail"
                    type="button"
                    class="ls-req-img-btn"
                    @click="openWorkingDiagram"
                  >
                    <img
                      v-if="workingPreviewThumbnail"
                      :src="workingPreviewThumbnail"
                      alt=""
                      class="ls-req-img"
                    />
                    <span
                      v-else
                      class="ls-muted"
                      ><I18nText k="learningSpace.noPreview"
                    /></span>
                  </button>
                  <p
                    v-else
                    class="ls-muted"
                  >
                    <I18nText k="learningSpace.noTemplatePreview" />
                  </p>
                  <button
                    type="button"
                    class="ls-btn ls-btn--ghost ls-btn--sm"
                    style="margin-top: 0.65rem"
                    :disabled="
                      openingCanvas || templateLoading || (!workingPreviewSpec && !isTeacherOwner)
                    "
                    @click="onOpenInCanvas"
                  >
                    <ExternalLink :size="14" />
                    <I18nText k="learningSpace.openTemplateInCanvas" />
                  </button>
                </div>
              </article>
              <article
                v-for="item in referenceDiagrams"
                :key="item.id"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">
                  <I18nText k="learningSpace.extraDiagramAsReference" />
                </p>
                <button
                  type="button"
                  class="ls-req-img-btn"
                  @click="openReferenceDiagram(item)"
                >
                  <img
                    v-if="item.thumbnail"
                    :src="item.thumbnail"
                    alt=""
                    class="ls-req-img"
                  />
                  <span
                    v-else
                    class="ls-muted"
                    >{{ item.title }}</span
                  >
                </button>
              </article>
              <article
                v-for="(src, idx) in assignment.instruction_images || []"
                :key="`img-${idx}`"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label"><I18nText k="learningSpace.instructionImage" /></p>
                <button
                  type="button"
                  class="ls-req-img-btn"
                  @click="openInstructionLightbox(idx)"
                >
                  <img
                    :src="instructionDisplaySrc(idx)"
                    alt=""
                    class="ls-req-img ls-req-img--photo"
                  />
                </button>
              </article>
            </div>
          </section>

          <section class="ls-req-section">
            <h3><I18nText k="learningSpace.instructions" /></h3>
            <p class="ls-req-body">
              <template v-if="assignment.instructions">{{ assignment.instructions }}</template
              ><I18nText
                v-else
                k="learningSpace.noInstructions"
              />
            </p>
          </section>

          <section class="ls-req-section">
            <h3><I18nText k="learningSpace.reqAi" /></h3>
            <p class="ls-req-body">
              <I18nText
                v-if="perms.ai_assist"
                k="learningSpace.aiAssistOn"
              /><I18nText
                v-else
                k="learningSpace.aiAssistOff"
              />
            </p>
            <ul
              v-if="perms.ai_assist && enabledTools.length"
              class="ls-req-chips"
            >
              <li
                v-for="label in enabledTools"
                :key="label"
              >
                {{ label }}
              </li>
            </ul>
            <p
              v-else-if="perms.ai_assist"
              class="ls-muted"
            >
              <I18nText k="learningSpace.aiToolsNone" />
            </p>
          </section>

          <section class="ls-req-section">
            <h3><I18nText k="learningSpace.eval.title" /></h3>
            <ul
              v-if="evalDims.length"
              class="ls-req-chips"
            >
              <li
                v-for="dim in evalDims"
                :key="dim"
              >
                {{ dimLabel(dim) }}
              </li>
            </ul>
            <p
              v-else
              class="ls-muted"
            >
              <I18nText k="learningSpace.noEvalDims" />
            </p>
          </section>
        </div>
        <footer class="ls-modal__foot">
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            @click="onClose"
          >
            <I18nText k="common.close" />
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
  <Teleport to="body">
    <div
      v-if="lightboxSrc"
      class="ls-req-lightbox"
      role="dialog"
      aria-modal="true"
      @click.self="closeImageLightbox"
    >
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-req-lightbox__close"
        :aria-label="t('common.close')"
        @click="closeImageLightbox"
      >
        <X :size="18" />
      </button>
      <img
        :src="lightboxSrc"
        alt=""
      />
    </div>
  </Teleport>
  <Teleport to="body">
    <div
      v-if="diagramLightbox"
      class="ls-req-lightbox"
      role="dialog"
      aria-modal="true"
      @click.self="closeDiagramLightbox"
    >
      <button
        type="button"
        class="ls-btn ls-btn--ghost ls-req-lightbox__close"
        :aria-label="t('common.close')"
        @click="closeDiagramLightbox"
      >
        <X :size="18" />
      </button>
      <div
        class="ls-req-template__frame ls-req-template__frame--fs"
        style="width: min(96vw, 1200px)"
        @click.stop
      >
        <ShowcaseInlineDiagramPreview
          v-if="diagramLightbox.spec"
          browse
          tight-fit
          :spec="diagramLightbox.spec"
          :diagram-type="null"
          :thumbnail-url="diagramLightbox.thumbnail"
        />
        <img
          v-else-if="diagramLightbox.thumbnail"
          :src="diagramLightbox.thumbnail"
          alt=""
          class="ls-req-img"
        />
      </div>
    </div>
  </Teleport>
</template>
