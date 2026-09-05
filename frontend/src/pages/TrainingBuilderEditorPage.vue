<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ElMessageBox } from 'element-plus'

import TrainingBuilderFilmstrip from '@/components/training/TrainingBuilderFilmstrip.vue'
import TrainingBuilderHeader from '@/components/training/TrainingBuilderHeader.vue'
import TrainingBuilderInfoDialog from '@/components/training/TrainingBuilderInfoDialog.vue'
import TrainingBuilderNotes from '@/components/training/TrainingBuilderNotes.vue'
import TrainingBuilderStage from '@/components/training/TrainingBuilderStage.vue'
import TrainingBuilderToolbar from '@/components/training/TrainingBuilderToolbar.vue'
import TrainingTeacherPreview from '@/components/training/TrainingTeacherPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import {
  addOverlay,
  applyPageKey,
  blankPageStep,
  blankSlideStep,
  insertStepsAt,
  selectedIndexAfterRemove,
  trainingCourseWriteBody,
} from '@/composables/training/trainingBuilderSteps'
import {
  advancePlayCursor,
  canAdvancePlayCursor,
  currentMarkStep,
} from '@/composables/training/trainingMarkSteps'
import { useTrainingAuthoringBind } from '@/composables/training/useTrainingAuthoringBind'
import { useTrainingBuilderThumbs } from '@/composables/training/useTrainingBuilderThumbs'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import type { TrainingCourse, TrainingCourseStep } from '@/types/training'
import { fetchTrainingCourse, saveTrainingCourse } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
const route = useRoute()

const courseId = computed(() => String(route.params.courseId || ''))
const title = ref('')
const description = ref('')
const steps = ref<TrainingCourseStep[]>([])
const selected = ref(0)
const busy = ref(false)
const infoOpen = ref(false)
const previewing = ref(false)
const previewFree = ref(false)

const current = computed(() => steps.value[selected.value] || null)
const {
  thumbs,
  awake,
  rememberIfNeeded,
  persistAllPending,
  hydrateFromSteps,
  removeThumb,
  insertThumbs,
  wake,
  applySelectAwake,
} = useTrainingBuilderThumbs(selected, current, steps, courseId)

const stageThumb = computed(() => thumbs.value[selected.value] || current.value?.asset_url || null)
const hibernated = computed(() => !awake.value && Boolean(stageThumb.value))

useTrainingAuthoringBind(current)

watch(previewing, (open) => {
  if (!open) previewFree.value = false
})

watch(
  () => ({
    awake: awake.value,
    selected: selected.value,
    modal: current.value?.modal_key ?? null,
    focus: current.value?.focus_key ?? null,
  }),
  (next) => {
    if (!next.awake) return
    void nextTick().then(() =>
      applyTrainingUiTarget({
        modalKey: next.modal,
        focusKey: next.focus,
      })
    )
  }
)

async function selectStep(index: number): Promise<void> {
  if (index === selected.value) return
  await rememberIfNeeded()
  applySelectAwake(index, steps.value[index])
  selected.value = index
}

async function addSlide(): Promise<void> {
  await rememberIfNeeded()
  steps.value.push(blankPageStep(steps.value.length))
  applySelectAwake(steps.value.length - 1, steps.value[steps.value.length - 1])
  selected.value = steps.value.length - 1
}

function removeStep(index: number): void {
  steps.value.splice(index, 1)
  removeThumb(index)
  if (!steps.value.length) {
    void addSlide()
    return
  }
  const next = selectedIndexAfterRemove(selected.value, index, steps.value.length)
  selected.value = next
  applySelectAwake(next, steps.value[next])
}

async function onUpload(role: 'cover' | 'slide', file: File | undefined): Promise<void> {
  if (!file) return
  const uploaded = await uploadTrainingFile(courseId.value, role, file)
  if (role === 'cover') {
    notify.success(t('training.builder.saved'))
    return
  }
  if (current.value) {
    wake()
    current.value.asset_id = uploaded.id
    current.value.asset_url = uploaded.url
  }
}

async function addImageSlides(files: File[]): Promise<void> {
  if (!files.length) return
  busy.value = true
  try {
    await rememberIfNeeded()
    const at = selected.value
    const created: TrainingCourseStep[] = []
    for (const file of files) {
      const uploaded = await uploadTrainingFile(courseId.value, 'slide', file)
      const step = blankSlideStep(at + created.length)
      step.asset_id = uploaded.id
      step.asset_url = uploaded.url
      created.push(step)
    }
    const inserted = insertStepsAt(steps.value, at, created)
    insertThumbs(
      inserted,
      created.map((step) => step.asset_url || null)
    )
    applySelectAwake(inserted, created[0])
    selected.value = inserted
  } catch {
    notify.error(t('training.builder.uploadFailed'))
  } finally {
    busy.value = false
  }
}

async function save(): Promise<void> {
  busy.value = true
  try {
    await rememberIfNeeded()
    await persistAllPending()
    const saved = await saveTrainingCourse(
      courseId.value,
      trainingCourseWriteBody(title.value, description.value, steps.value)
    )
    applyCourse(saved, true)
    infoOpen.value = false
    notify.success(t('training.builder.saved'))
  } catch (error) {
    const detail = error instanceof Error ? error.message : ''
    notify.error(detail && detail !== 'save' ? detail : t('training.builder.saveFailed'))
  } finally {
    busy.value = false
  }
}

function applyCourse(course: TrainingCourse, keepThumbs = false): void {
  title.value = course.title
  description.value = course.description
  steps.value = (course.steps || []).map((step) => ({ ...step }))
  if (!keepThumbs) hydrateFromSteps(steps.value)
  if (!steps.value.length) {
    void addSlide()
  }
}

async function onAddText(): Promise<void> {
  if (!current.value) return
  try {
    const result = await ElMessageBox.prompt(
      t('training.builder.toolTextHint'),
      t('training.builder.toolText'),
      { confirmButtonText: t('training.builder.save'), cancelButtonText: t('common.cancel') }
    )
    const text = String(result.value || '').trim()
    if (text) addOverlay(current.value, 'text', { text })
  } catch {
    return
  }
}

const previewCanPrev = computed(() => canAdvancePlayCursor(steps.value, selected.value, -1))
const previewCanNext = computed(() => canAdvancePlayCursor(steps.value, selected.value, 1))

async function previewMove(delta: number): Promise<void> {
  const next = advancePlayCursor(steps.value, selected.value, delta)
  if (next !== selected.value) await selectStep(next)
}

function onTopicsDrop(pos: { x: number; y: number }): void {
  if (!current.value) return
  wake()
  const at = currentMarkStep(current.value)
  addOverlay(current.value, 'topics', {
    x: pos.x,
    y: pos.y,
    step: at >= 2 ? at : undefined,
  })
}

onMounted(async () => {
  const course = await fetchTrainingCourse(courseId.value)
  applyCourse(course)
})
</script>

<template>
  <div class="training-page">
    <TrainingBuilderHeader
      :current="t('training.builder')"
      show-save
      :busy="busy"
      :previewing="previewing"
      @save="save"
      @info="infoOpen = true"
      @preview="previewing = !previewing"
    />
    <TrainingBuilderInfoDialog
      v-model:open="infoOpen"
      v-model:title="title"
      v-model:description="description"
      :busy="busy"
      @cover="onUpload('cover', $event)"
      @save="save"
    />
    <div class="editor">
      <TrainingBuilderFilmstrip
        :steps="steps"
        :selected="selected"
        :thumbs="thumbs"
        :busy="busy"
        @select="selectStep"
        @add="addSlide"
        @images="addImageSlides"
        @remove="removeStep"
      />
      <section
        v-if="current"
        class="editor__main"
      >
        <TrainingBuilderToolbar
          :step="current"
          @awake="wake"
          @page="applyPageKey(current, $event)"
          @text="onAddText"
          @emoji="addOverlay(current, 'emoji', { glyph: $event })"
          @arrow="addOverlay(current, 'arrow', $event)"
          @spotlight="addOverlay(current, 'spotlight')"
          @image="onUpload('slide', $event)"
        />
        <TrainingBuilderStage
          :step="current"
          :index="selected"
          :thumb="stageThumb"
          :hibernated="hibernated"
          @wake="wake"
          @topics="onTopicsDrop"
        />
        <TrainingBuilderNotes :step="current" />
      </section>
      <TrainingTeacherPreview
        v-if="previewing && current"
        :step="current"
        :can-prev="previewCanPrev"
        :can-next="previewCanNext"
        :free="previewFree"
        @close="previewing = false"
        @prev="previewMove(-1)"
        @next="previewMove(1)"
        @free="previewFree = !previewFree"
      />
    </div>
  </div>
</template>

<style scoped>
.training-page {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #fafaf9;
}
.editor {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
}
.editor__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.85rem 1rem 1rem;
}
</style>
