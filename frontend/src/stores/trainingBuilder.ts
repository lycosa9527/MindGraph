import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import type { TrainingPageKey } from '@/config/trainingPages'
import {
  isTrainingMediaStep,
  shouldAwakeOnSelect,
} from '@/composables/training/trainingBuilderHibernate'
import {
  addOverlay,
  applyPageKey,
  blankPageStep,
  insertStepsAt,
  selectedIndexAfterRemove,
} from '@/composables/training/trainingBuilderSteps'
import {
  advancePlayCursor,
  canAdvancePlayCursor,
} from '@/composables/training/trainingMarkSteps'
import { trainingStepPageKey } from '@/composables/training/trainingStageThumb'
import type {
  TrainingCourse,
  TrainingCourseStep,
  TrainingStepOverlay,
} from '@/types/training'

export const useTrainingBuilderStore = defineStore('trainingBuilder', () => {
  const courseId = ref('')
  const title = ref('')
  const description = ref('')
  const steps = ref<TrainingCourseStep[]>([])
  const selected = ref(0)
  const busy = ref(false)
  const infoOpen = ref(false)
  const previewing = ref(false)
  const previewFree = ref(false)
  const thumbs = ref<(string | null)[]>([])
  const thumbKeys = ref<string[]>([])
  const awake = ref(true)
  const isSystem = ref(false)

  const current = computed(() => steps.value[selected.value] || null)
  const stageThumb = computed(
    () => thumbs.value[selected.value] || current.value?.asset_url || null
  )
  const hibernated = computed(() => !awake.value && Boolean(stageThumb.value))
  const previewCanPrev = computed(() =>
    canAdvancePlayCursor(steps.value, selected.value, -1)
  )
  const previewCanNext = computed(() =>
    canAdvancePlayCursor(steps.value, selected.value, 1)
  )

  function setCourseId(id: string): void {
    courseId.value = id
  }

  function setTitle(value: string): void {
    title.value = value
  }

  function setDescription(value: string): void {
    description.value = value
  }

  function setBusy(value: boolean): void {
    busy.value = value
  }

  function setInfoOpen(value: boolean): void {
    infoOpen.value = value
  }

  function setPreviewing(value: boolean): void {
    previewing.value = value
    if (!value) previewFree.value = false
  }

  function togglePreview(): void {
    setPreviewing(!previewing.value)
  }

  function setPreviewFree(value: boolean): void {
    previewFree.value = value
  }

  function togglePreviewFree(): void {
    previewFree.value = !previewFree.value
  }

  function setSelected(index: number): void {
    selected.value = index
  }

  function setAwake(value: boolean): void {
    awake.value = value
  }

  function wake(): void {
    awake.value = true
  }

  function applySelectAwake(index: number, step: TrainingCourseStep | null | undefined): void {
    awake.value = shouldAwakeOnSelect(thumbs.value[index], step)
  }

  function writeThumb(index: number, url: string | null, pageKey: string): void {
    if (index < 0 || !url) return
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    while (next.length <= index) next.push(null)
    while (keys.length <= index) keys.push('')
    next[index] = url
    keys[index] = pageKey
    thumbs.value = next
    thumbKeys.value = keys
  }

  function hydrateFromSteps(rows: TrainingCourseStep[]): void {
    thumbs.value = rows.map((step) => {
      if (step.thumb_url) return step.thumb_url
      return isTrainingMediaStep(step) ? step.asset_url || null : null
    })
    thumbKeys.value = rows.map((step, index) =>
      thumbs.value[index] ? trainingStepPageKey(step) : ''
    )
    awake.value = shouldAwakeOnSelect(thumbs.value[selected.value], rows[selected.value] || null)
  }

  function removeThumb(index: number): void {
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    next.splice(index, 1)
    keys.splice(index, 1)
    thumbs.value = next
    thumbKeys.value = keys
  }

  function insertThumbs(index: number, urls: (string | null)[]): void {
    if (!urls.length) return
    const next = thumbs.value.slice()
    const keys = thumbKeys.value.slice()
    const at = Math.max(0, index)
    while (next.length < at) next.push(null)
    while (keys.length < at) keys.push('')
    next.splice(at, 0, ...urls)
    keys.splice(at, 0, ...urls.map(() => ''))
    thumbs.value = next
    thumbKeys.value = keys
  }

  function applyCourse(course: TrainingCourse, keepThumbs = false): void {
    isSystem.value = Boolean(course.is_system)
    title.value = course.title
    description.value = course.description
    steps.value = (course.steps || []).map((step) => ({ ...step }))
    if (!keepThumbs) hydrateFromSteps(steps.value)
    if (!steps.value.length) {
      steps.value.push(blankPageStep(0))
      applySelectAwake(0, steps.value[0])
      selected.value = 0
    }
  }

  function pushBlankPage(): TrainingCourseStep {
    const step = blankPageStep(steps.value.length)
    steps.value.push(step)
    return step
  }

  function removeStepAt(index: number): number {
    steps.value.splice(index, 1)
    removeThumb(index)
    if (!steps.value.length) {
      const step = pushBlankPage()
      applySelectAwake(0, step)
      selected.value = 0
      return 0
    }
    const next = selectedIndexAfterRemove(selected.value, index, steps.value.length)
    selected.value = next
    applySelectAwake(next, steps.value[next])
    return next
  }

  function insertCreatedSteps(at: number, created: TrainingCourseStep[]): number {
    const inserted = insertStepsAt(steps.value, at, created)
    insertThumbs(
      inserted,
      created.map((step) => step.asset_url || null)
    )
    applySelectAwake(inserted, created[0])
    selected.value = inserted
    return inserted
  }

  function setCurrentAsset(assetId: string, assetUrl: string): void {
    const step = current.value
    if (!step) return
    wake()
    step.asset_id = assetId
    step.asset_url = assetUrl
  }

  function applyCurrentPage(key: TrainingPageKey): void {
    if (!current.value) return
    applyPageKey(current.value, key)
  }

  function addCurrentOverlay(
    kind: TrainingStepOverlay['kind'],
    extra: Partial<TrainingStepOverlay> = {}
  ): void {
    if (!current.value) return
    addOverlay(current.value, kind, extra)
  }

  function previewIndex(delta: number): number {
    return advancePlayCursor(steps.value, selected.value, delta)
  }

  function reset(): void {
    courseId.value = ''
    title.value = ''
    description.value = ''
    steps.value = []
    selected.value = 0
    busy.value = false
    infoOpen.value = false
    previewing.value = false
    previewFree.value = false
    thumbs.value = []
    thumbKeys.value = []
    awake.value = true
    isSystem.value = false
  }

  return {
    courseId,
    title,
    description,
    steps,
    selected,
    busy,
    infoOpen,
    previewing,
    previewFree,
    thumbs,
    thumbKeys,
    awake,
    isSystem,
    current,
    stageThumb,
    hibernated,
    previewCanPrev,
    previewCanNext,
    setCourseId,
    setTitle,
    setDescription,
    setBusy,
    setInfoOpen,
    setPreviewing,
    togglePreview,
    setPreviewFree,
    togglePreviewFree,
    setSelected,
    setAwake,
    wake,
    applySelectAwake,
    writeThumb,
    hydrateFromSteps,
    removeThumb,
    insertThumbs,
    applyCourse,
    pushBlankPage,
    removeStepAt,
    insertCreatedSteps,
    setCurrentAsset,
    applyCurrentPage,
    addCurrentOverlay,
    previewIndex,
    reset,
  }
})
