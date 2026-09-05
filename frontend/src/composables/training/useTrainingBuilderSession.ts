import { nextTick, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { applyTrainingUiTarget } from '@/composables/training/applyTrainingUiTarget'
import { uploadedSlideSteps } from '@/composables/training/trainingBuilderSteps'
import { requestTrainingModalsClose } from '@/composables/training/trainingCommands'
import { currentMarkStep } from '@/composables/training/trainingMarkSteps'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { useTrainingAuthoringBind } from '@/composables/training/useTrainingAuthoringBind'
import { useTrainingBuilderAutosave } from '@/composables/training/useTrainingBuilderAutosave'
import { useTrainingBuilderThumbs } from '@/composables/training/useTrainingBuilderThumbs'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { fetchTrainingCourse } from '@/utils/trainingApi'

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
  syncState: ReturnType<typeof useTrainingBuilderAutosave>['syncState']
}

export function useTrainingBuilderSession(): TrainingBuilderSessionApi {
  const { t } = useLanguage()
  const notify = useNotifications()
  const route = useRoute()
  const builder = useTrainingBuilderStore()
  const { rememberIfNeeded, persistAllPending } = useTrainingBuilderThumbs()
  const { flush, markClean, syncState } = useTrainingBuilderAutosave({ persistAllPending })

  useTrainingAuthoringBind()
  requestTrainingModalsClose()

  watch(
    () => ({
      awake: builder.awake,
      selected: builder.selected,
      modal: builder.current?.modal_key ?? null,
      focus: builder.current?.focus_key ?? null,
    }),
    (next) => {
      if (!next.awake || !builder.courseId || !builder.current) return
      void nextTick().then(() =>
        applyTrainingUiTarget({
          modalKey: next.modal,
          focusKey: next.focus,
          hostModals: false,
        })
      )
    }
  )

  async function selectStep(index: number): Promise<void> {
    if (index === builder.selected) return
    await rememberIfNeeded()
    builder.applySelectAwake(index, builder.steps[index])
    builder.setSelected(index)
  }

  async function addSlide(): Promise<void> {
    await rememberIfNeeded()
    const step = builder.pushBlankPage()
    const index = builder.steps.length - 1
    builder.applySelectAwake(index, step)
    builder.setSelected(index)
  }

  async function removeStep(index: number): Promise<void> {
    if (builder.steps.length <= 1) {
      await rememberIfNeeded()
    }
    builder.removeStepAt(index)
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
      notify.success(t('training.builder.saved'))
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
      const at = builder.selected
      const uploaded: Array<{ id: string; url: string }> = []
      for (const file of files) {
        uploaded.push(await uploadTrainingFile(builder.courseId, 'slide', file))
      }
      builder.insertCreatedSteps(at, uploadedSlideSteps(at, uploaded))
    } catch (error) {
      notify.error(uploadFailedMessage(error))
    } finally {
      builder.setBusy(false)
    }
  }

  async function save(): Promise<void> {
    builder.setBusy(true)
    try {
      await rememberIfNeeded()
      await flush()
      builder.setInfoOpen(false)
      notify.success(t('training.builder.saved'))
    } catch (error) {
      const detail = error instanceof Error ? error.message : ''
      notify.error(detail && detail !== 'save' ? detail : t('training.builder.saveFailed'))
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
      builder.reset()
      builder.setCourseId(id)
      if (!id) return
      const course = await fetchTrainingCourse(id)
      if (token !== loadGeneration) return
      builder.applyCourse(course)
      markClean()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    loadGeneration += 1
    requestTrainingModalsClose()
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
    syncState,
  }
}
