import { nextTick, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { refreshUserDropdownMenu } from '@/composables/sidebar/useUserDropdownMenu'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import {
  clearBuilderDiagramBinding,
  isBoundToStep,
  noteBuilderStepRemoved,
  noteBuilderStepsInserted,
  syncBoundBuilderStep,
} from '@/composables/training/builderDiagramBridge'
import { uploadedSlideSteps } from '@/composables/training/trainingBuilderSteps'
import { requestTrainingModalsClose } from '@/composables/training/trainingCommands'
import { currentMarkStep } from '@/composables/training/trainingMarkSteps'
import {
  applyTrainingUiLock,
  armTrainingUiLock,
  captureOpenTrainingUiLock,
  releaseTrainingUiLock,
  takeArmedTrainingUiLock,
} from '@/composables/training/trainingUiLock'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { useTrainingAuthoringBind } from '@/composables/training/useTrainingAuthoringBind'
import { useTrainingBuilderAutosave } from '@/composables/training/useTrainingBuilderAutosave'
import { useTrainingBuilderSaveStatus } from '@/composables/training/useTrainingBuilderSaveStatus'
import { flushPublishedBuilderSpec } from '@/composables/training/trainingCanvasSpec'
import { useTrainingBuilderThumbs } from '@/composables/training/useTrainingBuilderThumbs'
import { TRAINING_MODALS } from '@/config/trainingUiTargets'
import { useTrainingStore } from '@/stores/training'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { fetchTrainingCourse, saveTrainingCourseMenu } from '@/utils/trainingApi'

export type TrainingBuilderSessionApi = {
  selectStep: (index: number) => Promise<void>
  addSlide: () => Promise<void>
  removeStep: (index: number) => Promise<void>
  onUpload: (role: 'cover' | 'slide', file: File | undefined) => Promise<void>
  addImageSlides: (files: File[]) => Promise<void>
  save: () => Promise<void>
  onAddText: () => void
  previewMove: (delta: number) => Promise<void>
  onTopicsDrop: (pos: { x: number; y: number }) => void
  onLockArm: () => void
  onLock: (index: number) => void
  saveLabel: ReturnType<typeof useTrainingBuilderSaveStatus>['saveLabel']
  saveTone: ReturnType<typeof useTrainingBuilderSaveStatus>['saveTone']
}

export function useTrainingBuilderSession(): TrainingBuilderSessionApi {
  const { t } = useLanguage()
  const notify = useNotifications()
  const route = useRoute()
  const builder = useTrainingBuilderStore()
  const { rememberIfNeeded, persistAllPending } = useTrainingBuilderThumbs()
  const { flush, markClean, syncState, lastSavedAt, isDirty } = useTrainingBuilderAutosave({
    persistAllPending,
  })
  const { saveLabel, saveTone } = useTrainingBuilderSaveStatus(syncState, lastSavedAt, isDirty)

  useTrainingAuthoringBind()
  requestTrainingModalsClose()

  watch(
    () => ({
      awake: builder.awake,
      selected: builder.selected,
      modal: builder.current?.modal_key ?? null,
      focus: builder.current?.focus_key ?? null,
      lock: builder.current?.ui_lock ?? null,
    }),
    (next) => {
      if (!next.awake || !builder.courseId || !builder.current) return
      void nextTick().then(() =>
        applyTrainingUiTarget({
          modalKey: next.modal,
          focusKey: next.focus,
          uiLock: next.lock || next.modal,
          hostModals: false,
        })
      )
    }
  )

  async function selectStep(index: number): Promise<void> {
    if (index === builder.selected) return
    await rememberIfNeeded()
    flushPublishedBuilderSpec()
    builder.applySelectAwake(index, builder.steps[index])
    builder.setSelected(index)
  }

  async function addSlide(): Promise<void> {
    await rememberIfNeeded()
    flushPublishedBuilderSpec()
    const step = builder.pushBlankPage()
    const index = builder.steps.length - 1
    builder.applySelectAwake(index, step)
    builder.setSelected(index)
    syncBoundBuilderStep(builder.steps)
  }

  async function removeStep(index: number): Promise<void> {
    const removed = builder.steps[index]
    if (builder.steps.length <= 1) {
      await rememberIfNeeded()
    }
    flushPublishedBuilderSpec()
    if (isBoundToStep(removed)) clearBuilderDiagramBinding()
    else noteBuilderStepRemoved(index)
    builder.removeStepAt(index)
    syncBoundBuilderStep(builder.steps)
  }

  function uploadFailedMessage(error: unknown): string {
    const detail = error instanceof Error ? error.message : ''
    if (!detail || detail === 'init' || detail === 'complete' || detail === 'empty') {
      return t('training.builder.uploadFailed')
    }
    return detail
  }

  async function onUpload(role: 'cover' | 'slide', file: File | undefined): Promise<void> {
    if (!file) return
    if (role === 'slide') {
      await addImageSlides([file])
      return
    }
    builder.setBusy(true)
    try {
      await uploadTrainingFile(builder.courseId, role, file)
      notify.successKey('training.builder.coverUploaded')
    } catch (error) {
      notify.error(uploadFailedMessage(error))
    } finally {
      builder.setBusy(false)
    }
  }

  async function addImageSlides(files: File[]): Promise<void> {
    if (!files.length) return
    builder.setBusy(true)
    try {
      await rememberIfNeeded()
      flushPublishedBuilderSpec()
      const at = builder.selected
      const uploaded = await Promise.all(
        files.map((file) => uploadTrainingFile(builder.courseId, 'slide', file))
      )
      builder.insertCreatedSteps(at, uploadedSlideSteps(at, uploaded))
      noteBuilderStepsInserted(at, uploaded.length)
      syncBoundBuilderStep(builder.steps)
    } catch (error) {
      notify.error(uploadFailedMessage(error))
    } finally {
      builder.setBusy(false)
    }
  }

  function menuSaveError(error: unknown): string {
    const detail = error instanceof Error ? error.message : ''
    if (detail === 'user_dropdown_label_too_long') return t('training.builder.menuLabelTooLong')
    if (detail === 'user_dropdown_limit') return t('training.builder.menuLabelLimit')
    return detail && detail !== 'menu' && detail !== 'save'
      ? detail
      : t('training.builder.saveFailed')
  }

  async function save(): Promise<void> {
    builder.setBusy(true)
    try {
      await rememberIfNeeded()
      await flush()
      const label = await saveTrainingCourseMenu(builder.courseId, builder.menuLabel)
      builder.setMenuLabel(label)
      void refreshUserDropdownMenu()
      builder.setInfoOpen(false)
      notify.successKey('training.builder.saved')
    } catch (error) {
      notify.error(menuSaveError(error))
    } finally {
      builder.setBusy(false)
    }
  }

  function onAddText(): void {
    if (!builder.current) return
    builder.wake()
    builder.addCurrentOverlay('text', { text: '' })
  }

  async function previewMove(delta: number): Promise<void> {
    const next = builder.previewIndex(delta)
    if (next !== builder.selected) await selectStep(next)
  }

  function onLock(index: number): void {
    const armed = takeArmedTrainingUiLock()
    const step = builder.steps[index]
    if (!step) return
    if (step.ui_lock || step.modal_key) {
      step.ui_lock = null
      step.modal_key = null
      if (index === builder.selected) {
        applyTrainingUiLock(null)
        requestTrainingModalsClose()
      }
      return
    }
    if (index !== builder.selected) {
      notify.warningKey('training.builder.lockNeedStep')
      return
    }
    const key = armed || captureOpenTrainingUiLock()
    if (!key) {
      notify.warningKey('training.builder.lockEmpty')
      return
    }
    const modal = TRAINING_MODALS.some((item) => item.key === key)
    if (modal) step.modal_key = key
    else step.ui_lock = key
    applyTrainingUiLock(key)
  }

  function onTopicsDrop(pos: { x: number; y: number }): void {
    if (!builder.current) return
    builder.wake()
    const at = currentMarkStep(builder.current)
    builder.addCurrentOverlay('topics', {
      x: pos.x,
      y: pos.y,
      step: at >= 2 ? at : undefined,
    })
  }

  let loadGeneration = 0

  watch(
    () => String(route.params.courseId || ''),
    async (id) => {
      const token = (loadGeneration += 1)
      flushPublishedBuilderSpec()
      clearBuilderDiagramBinding()
      builder.reset()
      builder.setCourseId(id)
      if (!id) return
      const course = await fetchTrainingCourse(id)
      if (token !== loadGeneration) return
      builder.applyCourse(course)
      markClean(course.updated_at)
    },
    { immediate: true }
  )

  onUnmounted(() => {
    loadGeneration += 1
    requestTrainingModalsClose()
    if (useTrainingStore().snapshot.state !== 'live') releaseTrainingUiLock()
    flushPublishedBuilderSpec()
    clearBuilderDiagramBinding()
    builder.reset()
  })

  return {
    selectStep,
    addSlide,
    removeStep,
    onUpload,
    addImageSlides,
    save,
    onAddText,
    previewMove,
    onTopicsDrop,
    onLockArm: armTrainingUiLock,
    onLock,
    saveLabel,
    saveTone,
  }
}
