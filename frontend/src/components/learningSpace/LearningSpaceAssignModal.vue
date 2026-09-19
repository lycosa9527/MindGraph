<script setup lang="ts">
/**
 * Teacher 「布置作业」 — 3-step modal (content → scoring → publish).
 */
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight, Paperclip, Plus, X } from '@lucide/vue'

import ShowcaseHistoryDiagramPicker from '@/components/showcase/ShowcaseHistoryDiagramPicker.vue'
import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import type { LsReferenceDiagram } from '@/composables/learningSpace/lsHelpers'
import { useSavedDiagramsStore } from '@/stores'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import {
  LS_MAX_INSTRUCTION_IMAGES,
  useLsInstructionImages,
} from '@/composables/learningSpace/lsInstructionImages'
import type { LearningClassRow } from '@/utils/learningSpaceApi'
import { createTeacherAssignment } from '@/utils/learningSpaceApi'
import {
  decodeMgUploadSpec,
  inferDiagramTypeFromSpec,
} from '@/utils/showcaseDiagramThumbnail'

const MAX_INSTRUCTION_IMAGES = LS_MAX_INSTRUCTION_IMAGES
const MAX_REFERENCE_DIAGRAMS = 5

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

type AiToolKey = (typeof AI_TOOL_KEYS)[number]

/** Official recommended scoring dimensions by thinking-map type. */
const DIAGRAM_SCORE_PRESETS: Record<string, string[]> = {
  circle_map: ['数量多', '角度广', '画规范'],
  bubble_map: ['数量多', '角度广', '画规范'],
  double_bubble_map: ['数量多', '角度广', '画规范'],
  tree_map: ['分合理', '画规范'],
  brace_map: ['拆完全', '层次清', '画规范'],
  flow_map: ['有条理', '写清晰', '画规范'],
  multi_flow_map: ['数量多', '角度广', '画规范'],
  bridge_map: ['关系明', '数量多', '画规范'],
  mind_map: ['主题明确', '结构清晰', '绘制规范'],
  mindmap: ['主题明确', '结构清晰', '绘制规范'],
}

const DIAGRAM_TYPE_OPTIONS: { value: string; labelKey: string }[] = [
  { value: 'circle_map', labelKey: 'learningSpace.diagramType.circle_map' },
  { value: 'bubble_map', labelKey: 'learningSpace.diagramType.bubble_map' },
  { value: 'double_bubble_map', labelKey: 'learningSpace.diagramType.double_bubble_map' },
  { value: 'tree_map', labelKey: 'learningSpace.diagramType.tree_map' },
  { value: 'brace_map', labelKey: 'learningSpace.diagramType.brace_map' },
  { value: 'flow_map', labelKey: 'learningSpace.diagramType.flow_map' },
  { value: 'multi_flow_map', labelKey: 'learningSpace.diagramType.multi_flow_map' },
  { value: 'bridge_map', labelKey: 'learningSpace.diagramType.bridge_map' },
  { value: 'mind_map', labelKey: 'learningSpace.diagramType.mind_map' },
]

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  classes: LearningClassRow[]
}>()

const emit = defineEmits(['created'])

const { t } = useLanguage()
const notify = useNotifications()
const savedDiagramsStore = useSavedDiagramsStore()

const step = ref<1 | 2 | 3>(1)
const showDiagramPicker = ref(false)
const saving = ref(false)
const customDimInput = ref('')
const modalBodyRef = ref<HTMLElement | null>(null)
const attachBlockRef = ref<HTMLElement | null>(null)

const form = ref({
  title: '',
  instructions: '',
  diagram_type: '',
  template_diagram_id: '',
  template_label: '',
  template_thumbnail: '' as string | null,
  template_spec: null as Record<string, unknown> | null,
  instruction_images: [] as string[],
  reference_diagrams: [] as LsReferenceDiagram[],
  evaluation_dimensions: [] as string[],
  class_ids: [] as number[],
  ai_assist: false,
  ai_tools: Object.fromEntries(AI_TOOL_KEYS.map((k) => [k, false])) as Record<AiToolKey, boolean>,
  due_at: '',
  late_policy: 'allow' as 'allow' | 'deny',
  teacher_provided_template: false,
  template_role: 'reference' as 'reference' | 'scaffold',
})

const instructionImages = computed({
  get: () => form.value.instruction_images,
  set: (value: string[]) => {
    form.value.instruction_images = value
  },
})
const instructionImagesCtl = useLsInstructionImages(instructionImages)

const publishableClasses = computed(() =>
  props.classes.filter((c) => c.status !== 'archived' && c.can_publish !== false)
)

const selectedStudentTotal = computed(() =>
  publishableClasses.value
    .filter((c) => form.value.class_ids.includes(c.id))
    .reduce((sum, c) => sum + (c.student_count || 0), 0)
)

const hasDiagramPreview = computed(
  () => Boolean(form.value.template_spec) || Boolean(form.value.template_thumbnail)
)

const hasReferenceMaterials = computed(
  () => form.value.instruction_images.length > 0 || form.value.reference_diagrams.length > 0
)

const imagesAtCap = computed(() => form.value.instruction_images.length >= MAX_INSTRUCTION_IMAGES)

const previewDiagramType = computed(() =>
  form.value.template_spec
    ? inferDiagramTypeFromSpec(form.value.template_spec, form.value.diagram_type)
    : form.value.diagram_type
)

const recommendedDims = computed(
  () => DIAGRAM_SCORE_PRESETS[form.value.diagram_type] ?? DIAGRAM_SCORE_PRESETS.mind_map
)

/** Recommended chips plus any custom selected dims (single row). */
const scoreDimChips = computed(() => {
  const recommended = recommendedDims.value
  const extras = form.value.evaluation_dimensions.filter((dim) => !recommended.includes(dim))
  return [...recommended, ...extras]
})

watch(visible, (open) => {
  if (!open) return
  step.value = 1
  if (form.value.class_ids.length === 0 && publishableClasses.value.length) {
    form.value.class_ids = [publishableClasses.value[0].id]
  }
  if (form.value.evaluation_dimensions.length === 0 && form.value.diagram_type) {
    applyRecommendedDims(form.value.diagram_type)
  }
})

function emptyAiTools(): Record<AiToolKey, boolean> {
  return Object.fromEntries(AI_TOOL_KEYS.map((k) => [k, false])) as Record<AiToolKey, boolean>
}

function applyRecommendedDims(diagramType: string): void {
  form.value.evaluation_dimensions = [
    ...(DIAGRAM_SCORE_PRESETS[diagramType] ?? DIAGRAM_SCORE_PRESETS.mind_map),
  ]
}

function onDiagramTypeChange(): void {
  applyRecommendedDims(form.value.diagram_type)
}

function resetForm(): void {
  step.value = 1
  customDimInput.value = ''
  instructionImagesCtl.clearImages()
  form.value = {
    title: '',
    instructions: '',
    diagram_type: '',
    template_diagram_id: '',
    template_label: '',
    template_thumbnail: null,
    template_spec: null,
    instruction_images: [] as string[],
    reference_diagrams: [],
    evaluation_dimensions: [],
    class_ids: publishableClasses.value[0] ? [publishableClasses.value[0].id] : [],
    ai_assist: false,
    ai_tools: emptyAiTools(),
    due_at: '',
    late_policy: 'allow',
    teacher_provided_template: false,
    template_role: 'reference',
  }
}

function toggleClass(id: number): void {
  const idx = form.value.class_ids.indexOf(id)
  if (idx >= 0) form.value.class_ids.splice(idx, 1)
  else form.value.class_ids.push(id)
}

function addCustomDim(): void {
  const label = customDimInput.value.trim()
  if (!label) return
  if (!form.value.evaluation_dimensions.includes(label)) {
    form.value.evaluation_dimensions.push(label)
  }
  customDimInput.value = ''
}

function removeDim(label: string): void {
  const idx = form.value.evaluation_dimensions.indexOf(label)
  if (idx >= 0) form.value.evaluation_dimensions.splice(idx, 1)
}

async function scrollAttachBlockToTop(): Promise<void> {
  await nextTick()
  await nextTick()
  requestAnimationFrame(() => {
    const body = modalBodyRef.value
    const block = attachBlockRef.value
    if (!body || !block) return
    const delta = block.getBoundingClientRect().top - body.getBoundingClientRect().top
    body.scrollTo({ top: body.scrollTop + delta, behavior: 'smooth' })
  })
}

function clearDiagramAttachment(): void {
  form.value.template_diagram_id = ''
  form.value.template_label = ''
  form.value.template_thumbnail = null
  form.value.template_spec = null
  form.value.teacher_provided_template = false
  form.value.template_role = 'reference'
}

function syncTypeFromSpec(spec: Record<string, unknown>): void {
  const inferred = inferDiagramTypeFromSpec(spec, form.value.diagram_type)
  const normalized = inferred === 'mindmap' ? 'mind_map' : inferred
  if (DIAGRAM_SCORE_PRESETS[normalized]) {
    form.value.diagram_type = normalized
    applyRecommendedDims(normalized)
  }
}

function diagramAlreadyAttached(diagramId: string): boolean {
  if (form.value.template_diagram_id === diagramId) return true
  return form.value.reference_diagrams.some((item) => item.id === diagramId)
}

function pushReferenceDiagram(item: LsReferenceDiagram): boolean {
  if (diagramAlreadyAttached(item.id)) {
    notify.warning(t('learningSpace.attachDiagramExists'))
    return false
  }
  if (form.value.reference_diagrams.length >= MAX_REFERENCE_DIAGRAMS) {
    notify.warning(t('learningSpace.attachRefDiagramMax', { n: MAX_REFERENCE_DIAGRAMS }))
    return false
  }
  form.value.reference_diagrams.push(item)
  return true
}

function applyWorkingDiagram(diagram: SavedDiagram, spec: Record<string, unknown> | null): void {
  form.value.template_diagram_id = diagram.id
  form.value.template_label = diagram.title || diagram.id
  form.value.template_thumbnail = diagram.thumbnail
  form.value.template_spec = spec
  form.value.teacher_provided_template = true
  if (spec) syncTypeFromSpec(spec)
  else if (diagram.diagram_type) {
    const normalized = diagram.diagram_type === 'mindmap' ? 'mind_map' : diagram.diagram_type
    if (DIAGRAM_SCORE_PRESETS[normalized]) {
      form.value.diagram_type = normalized
      applyRecommendedDims(normalized)
    }
  }
}

async function onPickDiagram(diagram: SavedDiagram): Promise<void> {
  if (diagramAlreadyAttached(diagram.id)) {
    notify.warning(t('learningSpace.attachDiagramExists'))
    return
  }
  const asWorking = !form.value.teacher_provided_template
  if (asWorking) {
    form.value.teacher_provided_template = true
    form.value.template_diagram_id = diagram.id
    form.value.template_label = diagram.title || diagram.id
    form.value.template_thumbnail = diagram.thumbnail
  } else if (!pushReferenceDiagram({
    id: diagram.id,
    title: diagram.title || diagram.id,
    thumbnail: diagram.thumbnail,
  })) {
    return
  }
  await savedDiagramsStore.prefetchDiagramSpecs([diagram.id])
  const spec = savedDiagramsStore.getCachedDiagramSpec(diagram.id)
  if (asWorking) applyWorkingDiagram(diagram, spec)
  await scrollAttachBlockToTop()
}

async function onMgFileChange(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    const spec = await decodeMgUploadSpec(file)
    if (!spec) {
      notify.error(t('learningSpace.mgInvalid'))
      return
    }
    const asWorking = !form.value.teacher_provided_template
    if (asWorking) {
      form.value.teacher_provided_template = true
      syncTypeFromSpec(spec)
    }
    const diagramType =
      form.value.diagram_type === 'mindmap' ? 'mind_map' : form.value.diagram_type || 'mind_map'
    const title = form.value.title.trim() || t('learningSpace.templateFromMg')
    let saved
    try {
      saved = await savedDiagramsStore.saveDiagram(title, diagramType, spec)
    } catch {
      notifyDiagramSaveFailed()
      return
    }
    if (!saved?.id) {
      notifyDiagramSaveFailed()
      return
    }
    if (asWorking) {
      form.value.template_label = `${title} (.mg)`
      form.value.template_spec = spec
      form.value.template_diagram_id = saved.id
      form.value.template_thumbnail = saved.thumbnail
      form.value.teacher_provided_template = true
    } else {
      const added = pushReferenceDiagram({
        id: saved.id,
        title: `${title} (.mg)`,
        thumbnail: saved.thumbnail,
      })
      if (!added) return
    }
    notify.success(t('learningSpace.mgAttached'))
    await scrollAttachBlockToTop()
  } catch {
    notify.error(t('learningSpace.mgInvalid'))
  }
}

async function onImageFilesChange(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const incoming = Array.from(input.files || [])
  input.value = ''
  const { added, skipped, tooLarge } = instructionImagesCtl.addImageFiles(incoming)
  if (skipped) {
    notify.warning(t('learningSpace.attachImageMax', { n: MAX_INSTRUCTION_IMAGES }))
  } else if (tooLarge) {
    notify.warning(t('learningSpace.attachImageTooLarge'))
  }
  if (added > 0) await scrollAttachBlockToTop()
}

function removeInstructionImage(idx: number): void {
  instructionImagesCtl.removeImage(idx)
}

function removeReferenceDiagram(idx: number): void {
  form.value.reference_diagrams.splice(idx, 1)
}

function buildAiPermissions(): Record<string, unknown> {
  const tools = form.value.ai_assist ? { ...form.value.ai_tools } : emptyAiTools()
  const role = form.value.teacher_provided_template ? form.value.template_role : 'none'
  return {
    ai_assist: form.value.ai_assist,
    ...tools,
    diagram_type: form.value.diagram_type,
    has_teacher_template: form.value.teacher_provided_template,
    template_role: role,
    start_mode: role === 'scaffold' ? 'scaffold' : 'blank',
    evaluation_dimensions: [...form.value.evaluation_dimensions],
    allow_late_submit: form.value.late_policy === 'allow',
    remind_24h: false,
    reference_diagrams: form.value.reference_diagrams.map((item) => ({
      id: item.id,
      title: item.title,
      thumbnail:
        item.thumbnail && item.thumbnail.length <= 80_000 ? item.thumbnail : '',
    })),
  }
}

function validateStep1(): boolean {
  if (!form.value.title.trim()) {
    notify.warning(t('learningSpace.fillTitle'))
    return false
  }
  if (!form.value.diagram_type) {
    notify.warning(t('learningSpace.fillDiagramType'))
    return false
  }
  return true
}

function validateStep2(): boolean {
  if (form.value.evaluation_dimensions.length === 0) {
    notify.warning(t('learningSpace.fillScoreDims'))
    return false
  }
  return true
}

function validateStep3(): boolean {
  if (form.value.class_ids.length === 0) {
    notify.warning(t('learningSpace.fillClasses'))
    return false
  }
  return true
}

function goNext(): void {
  if (step.value === 1) {
    if (!validateStep1()) return
    step.value = 2
    return
  }
  if (step.value === 2) {
    if (!validateStep2()) return
    step.value = 3
  }
}

function goBack(): void {
  if (step.value === 3) step.value = 2
  else if (step.value === 2) step.value = 1
}

function blankSpecForType(title: string, diagramType: string): Record<string, unknown> {
  const topic = title.trim() || t('learningSpace.templateFromMg')
  const slot = '…'
  switch (diagramType) {
    case 'circle_map':
      return { topic, context: [slot] }
    case 'bubble_map':
      return { topic, attributes: [slot] }
    case 'double_bubble_map':
      return {
        left: topic,
        right: slot,
        similarities: [slot],
        left_differences: [slot],
        right_differences: [slot],
      }
    case 'tree_map':
      return { topic, children: [{ text: slot, children: [] }] }
    case 'brace_map':
      return { whole: topic, parts: [{ name: slot }] }
    case 'flow_map':
      return { title: topic, steps: [slot] }
    case 'multi_flow_map':
      return { event: topic, causes: [slot], effects: [slot] }
    case 'bridge_map':
      return { relating_factor: topic, analogies: [{ left: slot, right: slot }] }
    case 'concept_map':
      return {
        topic,
        concepts: [slot],
        relationships: [{ from: topic, to: slot }],
      }
    case 'mind_map':
    case 'mindmap':
    default:
      return { topic, children: [{ text: slot, children: [] }] }
  }
}

function notifyDiagramSaveFailed(): void {
  notify.error(savedDiagramsStore.error || t('learningSpace.saveFailed'))
}

async function ensureTemplateDiagramId(): Promise<string> {
  if (
    form.value.template_diagram_id &&
    !form.value.template_diagram_id.startsWith('local-')
  ) {
    return form.value.template_diagram_id
  }
  const title = form.value.title.trim() || t('learningSpace.templateFromMg')
  const diagramType =
    form.value.diagram_type === 'mindmap' ? 'mind_map' : form.value.diagram_type || 'mind_map'
  const spec = form.value.template_spec ?? blankSpecForType(title, diagramType)
  const saved = await savedDiagramsStore.saveDiagram(title, diagramType, spec)
  if (!saved?.id) {
    throw new Error(savedDiagramsStore.error || 'template diagram save failed')
  }
  form.value.template_diagram_id = saved.id
  form.value.template_thumbnail = saved.thumbnail
  form.value.template_label = form.value.template_label || title
  form.value.template_spec = spec
  return saved.id
}

async function submit(): Promise<void> {
  if (!validateStep1() || !validateStep2() || !validateStep3()) return
  saving.value = true
  try {
    const templateDiagramId = await ensureTemplateDiagramId()
    const due = form.value.due_at ? new Date(form.value.due_at).toISOString() : null
    const ai_permissions = buildAiPermissions()
    const instructionRefs = await instructionImagesCtl.uploadAll(form.value.class_ids[0])
    const payloadBase = {
      title: form.value.title.trim(),
      instructions: form.value.instructions.trim(),
      template_diagram_id: templateDiagramId,
      due_at: due,
      instruction_images: instructionRefs,
      ai_permissions,
      status: 'active' as const,
    }
    const classIds = form.value.class_ids.filter((id) =>
      publishableClasses.value.some((row) => row.id === id)
    )
    if (!classIds.length) {
      notify.warning(t('learningSpace.fillClasses'))
      return
    }
    for (const classId of classIds) {
      await createTeacherAssignment({
        ...payloadBase,
        class_id: classId,
      })
    }
    notify.success(t('learningSpace.assignmentCreated'))
    emit('created')
    resetForm()
    visible.value = false
  } catch (error) {
    const message =
      error instanceof Error && error.message
        ? error.message
        : savedDiagramsStore.error || t('learningSpace.saveFailed')
    notify.error(message)
  } finally {
    saving.value = false
  }
}

function onClose(): void {
  visible.value = false
}

function onBackdrop(): void {
  if (!saving.value) onClose()
}

function aiToolLabelKey(key: AiToolKey): string {
  return `learningSpace.aiTool.${key}`
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="ls-modal-overlay"
      @click.self="onBackdrop"
    >
      <div
        class="ls-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="t('learningSpace.createAssignment')"
      >
        <header class="ls-modal__head">
          <div class="ls-modal__head-text">
            <p class="ls-modal__eyebrow">{{ t('learningSpace.brandTitle') }}</p>
            <h2 class="ls-modal__title">{{ t('learningSpace.createAssignment') }}</h2>
          </div>
          <button
            type="button"
            class="ls-modal__close"
            :aria-label="t('common.close')"
            :disabled="saving"
            @click="onClose"
          >
            <X :size="18" />
          </button>
        </header>

        <div
          class="ls-modal__steps"
          aria-hidden="true"
        >
          <div
            class="ls-modal__step"
            :class="{ 'ls-modal__step--on': step === 1, 'ls-modal__step--done': step > 1 }"
          >
            <span class="ls-modal__step-num">1</span>
            <span class="ls-modal__step-label">{{ t('learningSpace.assign.stepContent') }}</span>
          </div>
          <div class="ls-modal__step-line" />
          <div
            class="ls-modal__step"
            :class="{ 'ls-modal__step--on': step === 2, 'ls-modal__step--done': step > 2 }"
          >
            <span class="ls-modal__step-num">2</span>
            <span class="ls-modal__step-label">{{ t('learningSpace.assign.stepScore') }}</span>
          </div>
          <div class="ls-modal__step-line" />
          <div
            class="ls-modal__step"
            :class="{ 'ls-modal__step--on': step === 3 }"
          >
            <span class="ls-modal__step-num">3</span>
            <span class="ls-modal__step-label">{{ t('learningSpace.assign.stepPublish') }}</span>
          </div>
        </div>

        <div
          ref="modalBodyRef"
          class="ls-modal__body"
        >
          <section
            v-show="step === 1"
            class="ls-modal__pane"
          >
            <label class="ls-field">
              {{ t('learningSpace.assignmentTitle') }}
              <input
                v-model="form.title"
                type="text"
                maxlength="200"
                :placeholder="t('learningSpace.assign.titlePlaceholder')"
              />
            </label>

            <label class="ls-field">
              {{ t('learningSpace.diagramTypeLabel') }}
              <select
                v-model="form.diagram_type"
                :class="{ 'ls-field__placeholder': !form.diagram_type }"
                @change="onDiagramTypeChange"
              >
                <option
                  value=""
                  disabled
                >
                  {{ t('learningSpace.fillDiagramType') }}
                </option>
                <option
                  v-for="opt in DIAGRAM_TYPE_OPTIONS"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ t(opt.labelKey) }}
                </option>
              </select>
            </label>

            <label class="ls-field">
              {{ t('learningSpace.instructions') }}
              <textarea
                v-model="form.instructions"
                rows="4"
                :placeholder="t('learningSpace.assign.reqPlaceholder')"
              />
            </label>

            <div
              ref="attachBlockRef"
              class="ls-modal__block"
            >
              <div class="ls-modal__block-head">
                <Paperclip :size="15" />
                <span>{{ t('learningSpace.attachments') }}</span>
                <span class="ls-modal__optional">{{ t('learningSpace.optional') }}</span>
              </div>
              <p class="ls-modal__hint">{{ t('learningSpace.attachmentsScaffoldHint') }}</p>
              <div class="ls-modal__attach-actions">
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="showDiagramPicker = true"
                >
                  {{ t('learningSpace.pickDiagram') }}
                </button>
                <label class="ls-btn ls-btn--ghost ls-btn--sm">
                  {{ t('learningSpace.attachMg') }}
                  <input
                    type="file"
                    accept=".mg,application/octet-stream"
                    hidden
                    @change="onMgFileChange"
                  />
                </label>
                <label
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  :class="{ 'ls-btn--disabled': imagesAtCap }"
                >
                  {{ t('learningSpace.uploadImages') }}
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    :disabled="imagesAtCap"
                    @change="onImageFilesChange"
                  />
                </label>
              </div>

              <div
                v-if="form.template_label || hasDiagramPreview"
                class="ls-modal__preview"
              >
                <div class="ls-modal__preview-head">
                  <span>{{ form.template_label || t('learningSpace.attachWorkingDiagram') }}</span>
                  <button
                    type="button"
                    class="ls-modal__thumb-rm"
                    @click="clearDiagramAttachment"
                  >
                    {{ t('common.delete') }}
                  </button>
                </div>
                <fieldset
                  v-if="form.teacher_provided_template"
                  class="ls-role-fieldset ls-role-fieldset--on-preview"
                >
                  <legend>{{ t('learningSpace.diagramUseLabel') }}</legend>
                  <div class="ls-role-grid">
                    <label
                      class="ls-role-card"
                      :class="{ 'ls-role-card--on': form.template_role === 'reference' }"
                    >
                      <input
                        v-model="form.template_role"
                        type="radio"
                        value="reference"
                      />
                      <span class="ls-role-card__body">
                        <strong>{{ t('learningSpace.diagramUseReference') }}</strong>
                        <em>{{ t('learningSpace.diagramUseReferenceHint') }}</em>
                      </span>
                    </label>
                    <label
                      class="ls-role-card"
                      :class="{ 'ls-role-card--on': form.template_role === 'scaffold' }"
                    >
                      <input
                        v-model="form.template_role"
                        type="radio"
                        value="scaffold"
                      />
                      <span class="ls-role-card__body">
                        <span class="ls-role-card__title">
                          <strong>{{ t('learningSpace.diagramUseScaffold') }}</strong>
                          <span class="ls-role-card__badge">{{
                            t('learningSpace.diagramUseScaffoldRecommend')
                          }}</span>
                        </span>
                        <em>{{ t('learningSpace.diagramUseScaffoldHint') }}</em>
                      </span>
                    </label>
                  </div>
                </fieldset>
                <div class="ls-modal__preview-frame">
                  <ShowcaseInlineDiagramPreview
                    v-if="form.template_spec"
                    :spec="form.template_spec"
                    :diagram-type="previewDiagramType"
                    :thumbnail-url="form.template_thumbnail"
                  />
                  <img
                    v-else-if="form.template_thumbnail"
                    :src="form.template_thumbnail"
                    alt=""
                    class="ls-modal__preview-img"
                  />
                </div>
              </div>

              <div
                v-if="hasReferenceMaterials"
                class="ls-modal__refs"
              >
                <div class="ls-modal__block-head">
                  <span>{{ t('learningSpace.attachReferenceMaterials') }}</span>
                  <span class="ls-modal__optional">{{
                    t('learningSpace.attachImageQuota', {
                      used: form.instruction_images.length,
                      n: MAX_INSTRUCTION_IMAGES,
                    })
                  }}</span>
                </div>
                <div class="ls-modal__thumbs">
                  <div
                    v-for="(item, idx) in form.reference_diagrams"
                    :key="item.id"
                    class="ls-modal__thumb"
                  >
                    <img
                      v-if="item.thumbnail"
                      :src="item.thumbnail"
                      alt=""
                    />
                    <div
                      v-else
                      class="ls-modal__thumb-ph"
                    >
                      {{ t('learningSpace.extraDiagramAsReference') }}
                    </div>
                    <p class="ls-modal__thumb-cap">
                      {{ item.title || t('learningSpace.extraDiagramAsReference') }}
                    </p>
                    <button
                      type="button"
                      class="ls-modal__thumb-rm"
                      @click="removeReferenceDiagram(idx)"
                    >
                      {{ t('common.delete') }}
                    </button>
                  </div>
                  <div
                    v-for="(src, idx) in form.instruction_images"
                    :key="`img-${idx}`"
                    class="ls-modal__thumb"
                  >
                    <img
                      :src="src"
                      alt=""
                    />
                    <p class="ls-modal__thumb-cap">{{ t('learningSpace.instructionImage') }}</p>
                    <button
                      type="button"
                      class="ls-modal__thumb-rm"
                      @click="removeInstructionImage(idx)"
                    >
                      {{ t('common.delete') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section
            v-show="step === 2"
            class="ls-modal__pane"
          >
            <div class="ls-modal__block">
              <div class="ls-modal__block-head">
                <span>{{ t('learningSpace.assign.stepScore') }}</span>
              </div>
              <p class="ls-modal__hint">
                {{
                  t('learningSpace.eval.diagramPresetHint', {
                    type: t(
                      `learningSpace.diagramType.${form.diagram_type === 'mindmap' ? 'mind_map' : form.diagram_type}`
                    ),
                  })
                }}
              </p>
              <div class="ls-chip-grid">
                <button
                  v-for="dim in scoreDimChips"
                  :key="`dim-${dim}`"
                  type="button"
                  class="ls-chip"
                  :class="{ 'ls-chip--on': form.evaluation_dimensions.includes(dim) }"
                  @click="
                    form.evaluation_dimensions.includes(dim) ? removeDim(dim) : form.evaluation_dimensions.push(dim)
                  "
                >
                  {{ dim
                  }}{{ form.evaluation_dimensions.includes(dim) ? ' ×' : '' }}
                </button>
              </div>
              <div class="ls-modal__custom-dim">
                <input
                  v-model="customDimInput"
                  type="text"
                  maxlength="40"
                  :placeholder="t('learningSpace.eval.customPlaceholder')"
                  @keydown.enter.prevent="addCustomDim"
                />
                <button
                  type="button"
                  class="ls-btn ls-btn--ghost ls-btn--sm"
                  @click="addCustomDim"
                >
                  <Plus :size="14" />
                  {{ t('learningSpace.eval.addCustom') }}
                </button>
              </div>
              <button
                type="button"
                class="ls-link"
                style="margin-top: 0.65rem"
                @click="applyRecommendedDims(form.diagram_type)"
              >
                {{ t('learningSpace.eval.resetRecommended') }}
              </button>
            </div>
          </section>

          <section
            v-show="step === 3"
            class="ls-modal__pane"
          >
            <div class="ls-modal__block">
              <div class="ls-modal__block-head">
                <span>{{ t('learningSpace.assign.sectionClasses') }}</span>
              </div>
              <p class="ls-modal__summary">
                {{
                  t('learningSpace.assign.selectedSummary', {
                    classes: form.class_ids.length,
                    students: selectedStudentTotal,
                  })
                }}
              </p>
              <div class="ls-modal__class-grid">
                <button
                  v-for="c in publishableClasses"
                  :key="c.id"
                  type="button"
                  class="ls-modal__class"
                  :class="{ 'ls-modal__class--on': form.class_ids.includes(c.id) }"
                  @click="toggleClass(c.id)"
                >
                  <span class="ls-modal__class-check" aria-hidden="true" />
                  <span class="ls-modal__class-meta">
                    <span class="ls-modal__class-name">{{ c.name }}</span>
                    <span class="ls-modal__class-count">
                      {{ t('learningSpace.studentCount', { n: c.student_count }) }}
                    </span>
                  </span>
                </button>
              </div>
            </div>

            <div class="ls-modal__block">
              <div class="ls-modal__block-head">
                <span>{{ t('learningSpace.aiLimits') }}</span>
              </div>
              <label class="ls-modal__toggle ls-modal__toggle--switch">
                <input
                  v-model="form.ai_assist"
                  type="checkbox"
                />
                <span>{{ t('learningSpace.aiAssistSwitch') }}</span>
              </label>
              <template v-if="form.ai_assist">
                <p class="ls-modal__hint">{{ t('learningSpace.aiLimitsHint') }}</p>
                <div class="ls-chip-grid">
                  <button
                    v-for="key in AI_TOOL_KEYS"
                    :key="key"
                    type="button"
                    class="ls-chip"
                    :class="{ 'ls-chip--on': form.ai_tools[key] }"
                    @click="form.ai_tools[key] = !form.ai_tools[key]"
                  >
                    {{ t(aiToolLabelKey(key)) }}
                  </button>
                </div>
              </template>
            </div>

            <label class="ls-field">
              {{ t('learningSpace.due') }}
              <input
                v-model="form.due_at"
                type="datetime-local"
              />
            </label>

            <div class="ls-seg">
              <button
                type="button"
                class="ls-seg__btn"
                :class="{ 'ls-seg__btn--on': form.late_policy === 'allow' }"
                @click="form.late_policy = 'allow'"
              >
                {{ t('learningSpace.allowLateYes') }}
              </button>
              <button
                type="button"
                class="ls-seg__btn"
                :class="{ 'ls-seg__btn--on': form.late_policy === 'deny' }"
                @click="form.late_policy = 'deny'"
              >
                {{ t('learningSpace.allowLateNo') }}
              </button>
            </div>
          </section>
        </div>

        <footer class="ls-modal__foot">
          <template v-if="step === 1">
            <button
              type="button"
              class="ls-btn ls-btn--ghost"
              :disabled="saving"
              @click="onClose"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="button"
              class="ls-btn ls-btn--primary"
              @click="goNext"
            >
              {{ t('learningSpace.assign.next') }}
              <ArrowRight :size="16" />
            </button>
          </template>
          <template v-else-if="step === 2">
            <button
              type="button"
              class="ls-btn ls-btn--ghost"
              :disabled="saving"
              @click="goBack"
            >
              <ArrowLeft :size="16" />
              {{ t('learningSpace.assign.prev') }}
            </button>
            <button
              type="button"
              class="ls-btn ls-btn--primary"
              @click="goNext"
            >
              {{ t('learningSpace.assign.next') }}
              <ArrowRight :size="16" />
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="ls-btn ls-btn--ghost"
              :disabled="saving"
              @click="goBack"
            >
              <ArrowLeft :size="16" />
              {{ t('learningSpace.assign.prev') }}
            </button>
            <button
              type="button"
              class="ls-btn ls-btn--primary"
              :disabled="saving"
              @click="submit"
            >
              {{ t('learningSpace.publishAssignment') }}
            </button>
          </template>
        </footer>
      </div>
    </div>
  </Teleport>

  <ShowcaseHistoryDiagramPicker
    v-model:visible="showDiagramPicker"
    variant="ls"
    multi-select
    @select="onPickDiagram"
  />
</template>
