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
  assignmentDiagramType,
  assignmentHasTeacherTemplate,
  assignmentIsClosed,
  assignmentReferenceDiagrams,
  assignmentTemplateRole,
  formatLsDateTime,
} from '@/composables/learningSpace/lsHelpers'
import { useAuthStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import {
  fetchAssignmentTemplatePreview,
  type LearningAssignment,
  type LearningTemplatePreview,
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

const diagramTypeSlug = computed(() => assignmentDiagramType(props.assignment))

const diagramTypeLabel = computed(() => t(`learningSpace.diagramType.${diagramTypeSlug.value}`))

const hasTeacherTemplate = computed(() =>
  assignmentHasTeacherTemplate(props.assignment, templatePreview.value?.preview_spec)
)

const templateRole = computed(() => assignmentTemplateRole(props.assignment))

const hasInstructionImages = computed(
  () => (props.assignment?.instruction_images ?? []).length > 0
)

const referenceDiagrams = computed(() => assignmentReferenceDiagrams(props.assignment))

const showStudentTemplate = computed(
  () =>
    hasTeacherTemplate.value ||
    (templateLoading.value &&
      (templateRole.value === 'reference' || templateRole.value === 'scaffold'))
)

const showStudentMaterials = computed(
  () =>
    hasInstructionImages.value ||
    showStudentTemplate.value ||
    referenceDiagrams.value.length > 0
)

function aiToolLabelKey(key: (typeof AI_TOOL_KEYS)[number]): string {
  return `learningSpace.aiTool.${key}`
}

function dimLabel(dim: string): string {
  const key = EVAL_PRESET_KEYS[dim]
  return key ? t(key) : dim
}

const modalTitle = computed(() =>
  isStudentAudience.value
    ? t('learningSpace.studentReqTitle')
    : t('learningSpace.viewRequirements')
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

const extraSpecs = ref<Record<string, Record<string, unknown>>>({})

async function loadTemplate(): Promise<void> {
  const a = props.assignment
  extraSpecs.value = {}
  if (!a) {
    templatePreview.value = null
    return
  }
  if (
    isStudentAudience.value &&
    (a.ai_permissions?.template_role === 'none' ||
      a.ai_permissions?.has_teacher_template === false)
  ) {
    templatePreview.value = null
  } else {
    templateLoading.value = true
    try {
      templatePreview.value = await fetchAssignmentTemplatePreview(a.id)
    } catch {
      templatePreview.value = null
    } finally {
      templateLoading.value = false
    }
  }
  const extraIds = assignmentReferenceDiagrams(a).map((item) => item.id)
  if (!extraIds.length) return
  await savedDiagramsStore.prefetchDiagramSpecs(extraIds)
  const next: Record<string, Record<string, unknown>> = {}
  for (const id of extraIds) {
    const spec = savedDiagramsStore.getCachedDiagramSpec(id)
    if (spec) next[id] = spec
  }
  extraSpecs.value = next
}

watch(
  () => [visible.value, props.assignment?.id] as const,
  ([open]) => {
    if (open && props.assignment) {
      void loadTemplate()
    }
  }
)

function onClose(): void {
  visible.value = false
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
    notify.error(t('learningSpace.noPreview'))
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
    notify.success(t('learningSpace.saveToLibraryOk'))
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
              <dt>{{ t('learningSpace.diagramTypeLabel') }}</dt>
              <dd>{{ diagramTypeLabel }}</dd>
            </div>
            <div v-if="assignment.due_at">
              <dt>{{ t('learningSpace.due') }}</dt>
              <dd>{{ formatLsDateTime(assignment.due_at) }}</dd>
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
              {{
                templateRole === 'scaffold'
                  ? t('learningSpace.studentReqScaffold')
                  : t('learningSpace.studentReqMaterials')
              }}
            </h3>
            <p class="ls-muted">
              {{
                templateRole === 'scaffold'
                  ? t('learningSpace.studentReqScaffoldHint')
                  : t('learningSpace.studentReqMaterialsHint')
              }}
            </p>
            <div
              v-if="showStudentTemplate"
              class="ls-req-template"
            >
              <div
                v-if="templateLoading"
                class="ls-req-template__loading"
              >
                <Loader2
                  class="animate-spin"
                  :size="20"
                />
              </div>
              <ShowcaseInlineDiagramPreview
                v-else-if="templatePreview?.preview_spec && hasTeacherTemplate"
                :spec="templatePreview.preview_spec"
                :thumbnail-url="templatePreview.thumbnail || assignment.template_thumbnail"
              />
              <img
                v-else-if="hasTeacherTemplate && (templatePreview?.thumbnail || assignment.template_thumbnail)"
                :src="templatePreview?.thumbnail || assignment.template_thumbnail || ''"
                alt=""
                class="ls-req-img"
              />
              <button
                v-if="hasTeacherTemplate"
                type="button"
                class="ls-btn ls-btn--ghost ls-btn--sm"
                style="margin-top: 0.65rem"
                :disabled="openingCanvas || templateLoading || !templatePreview?.preview_spec"
                @click="onOpenInCanvas"
              >
                <ExternalLink :size="14" />
                {{ t('learningSpace.studentReqOpenTemplate') }}
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
                <p class="ls-req-attach__label">{{ t('learningSpace.extraDiagramAsReference') }}</p>
                <ShowcaseInlineDiagramPreview
                  v-if="extraSpecs[item.id]"
                  :spec="extraSpecs[item.id]"
                  :thumbnail-url="item.thumbnail"
                />
                <img
                  v-else-if="item.thumbnail"
                  :src="item.thumbnail"
                  alt=""
                  class="ls-req-img"
                />
                <p
                  v-else
                  class="ls-muted"
                >
                  {{ item.title }}
                </p>
              </article>
              <article
                v-for="(src, idx) in assignment.instruction_images || []"
                :key="`img-${idx}`"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">{{ t('learningSpace.instructionImage') }}</p>
                <img
                  :src="src"
                  alt=""
                  class="ls-req-img ls-req-img--photo"
                />
              </article>
            </div>
          </section>
        </div>
        <div
          v-else
          class="ls-modal__body ls-req-scroll"
        >
          <section class="ls-req-section">
            <h3>{{ t('learningSpace.reqOverview') }}</h3>
            <dl class="ls-req-dl">
              <div>
                <dt>{{ t('learningSpace.class') }}</dt>
                <dd>{{ className }}</dd>
              </div>
              <div>
                <dt>{{ t('learningSpace.diagramTypeLabel') }}</dt>
                <dd>{{ diagramTypeLabel }}</dd>
              </div>
              <div>
                <dt>{{ t('learningSpace.status') }}</dt>
                <dd>{{ statusText }}</dd>
              </div>
              <div>
                <dt>{{ t('learningSpace.due') }}</dt>
                <dd>{{ formatLsDateTime(assignment.due_at) }}</dd>
              </div>
              <div>
                <dt>{{ t('learningSpace.publishedAt') }}</dt>
                <dd>{{ formatLsDateTime(assignment.created_at) }}</dd>
              </div>
              <div>
                <dt>{{ t('learningSpace.latePolicy') }}</dt>
                <dd>
                  {{
                    perms.allow_late_submit
                      ? t('learningSpace.allowLateYes')
                      : t('learningSpace.allowLateNo')
                  }}
                </dd>
              </div>
            </dl>
          </section>

          <section class="ls-req-section">
            <h3>{{ t('learningSpace.attachments') }}</h3>
            <p class="ls-muted">{{ t('learningSpace.templateMgHint') }}</p>
            <div class="ls-req-attach-list">
              <article class="ls-req-attach">
                <p class="ls-req-attach__label">{{ t('learningSpace.attachWorkingDiagram') }}</p>
                <div class="ls-req-template">
                  <div
                    v-if="templateLoading"
                    class="ls-req-template__loading"
                  >
                    <Loader2
                      class="animate-spin"
                      :size="20"
                    />
                  </div>
                  <ShowcaseInlineDiagramPreview
                    v-else-if="templatePreview?.preview_spec"
                    :spec="templatePreview.preview_spec"
                    :thumbnail-url="templatePreview.thumbnail || assignment.template_thumbnail"
                  />
                  <img
                    v-else-if="templatePreview?.thumbnail || assignment.template_thumbnail"
                    :src="templatePreview?.thumbnail || assignment.template_thumbnail || ''"
                    alt=""
                    class="ls-req-img"
                  />
                  <p
                    v-else
                    class="ls-muted"
                  >
                    {{ t('learningSpace.noTemplatePreview') }}
                  </p>
                  <button
                    type="button"
                    class="ls-btn ls-btn--ghost ls-btn--sm"
                    style="margin-top: 0.65rem"
                    :disabled="openingCanvas || templateLoading || (!templatePreview?.preview_spec && !isTeacherOwner)"
                    @click="onOpenInCanvas"
                  >
                    <ExternalLink :size="14" />
                    {{ t('learningSpace.openTemplateInCanvas') }}
                  </button>
                </div>
              </article>
              <article
                v-for="item in referenceDiagrams"
                :key="item.id"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">{{ t('learningSpace.extraDiagramAsReference') }}</p>
                <div class="ls-req-template">
                  <ShowcaseInlineDiagramPreview
                    v-if="extraSpecs[item.id]"
                    :spec="extraSpecs[item.id]"
                    :thumbnail-url="item.thumbnail"
                  />
                  <img
                    v-else-if="item.thumbnail"
                    :src="item.thumbnail"
                    alt=""
                    class="ls-req-img"
                  />
                  <p
                    v-else
                    class="ls-muted"
                  >
                    {{ item.title || t('learningSpace.noTemplatePreview') }}
                  </p>
                </div>
              </article>
              <article
                v-for="(src, idx) in assignment.instruction_images || []"
                :key="`img-${idx}`"
                class="ls-req-attach"
              >
                <p class="ls-req-attach__label">{{ t('learningSpace.instructionImage') }}</p>
                <img
                  :src="src"
                  alt=""
                  class="ls-req-img ls-req-img--photo"
                />
              </article>
            </div>
          </section>

          <section class="ls-req-section">
            <h3>{{ t('learningSpace.instructions') }}</h3>
            <p class="ls-req-body">
              {{ assignment.instructions || t('learningSpace.noInstructions') }}
            </p>
          </section>

          <section class="ls-req-section">
            <h3>{{ t('learningSpace.reqAi') }}</h3>
            <p class="ls-req-body">
              {{ perms.ai_assist ? t('learningSpace.aiAssistOn') : t('learningSpace.aiAssistOff') }}
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
              {{ t('learningSpace.aiToolsNone') }}
            </p>
          </section>

          <section class="ls-req-section">
            <h3>{{ t('learningSpace.eval.title') }}</h3>
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
              {{ t('learningSpace.noEvalDims') }}
            </p>
          </section>
        </div>
        <footer class="ls-modal__foot">
          <button
            type="button"
            class="ls-btn ls-btn--primary"
            @click="onClose"
          >
            {{ t('common.close') }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
