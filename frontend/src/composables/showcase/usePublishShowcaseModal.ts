/**
 * Publish / edit Showcase modal state and handlers.
 */
import { computed, ref, watch } from 'vue'

import { BookOpen, History, Image as ImageIcon, LayoutTemplate, Sparkles, Upload, X } from '@lucide/vue'

import {
  DIAGRAM_GALLERY_MAX_ITEMS,
} from '@/components/showcase/showcaseGallery'
import {
  CASE_TYPE_PUBLISH_OPTIONS,
  CASE_ATTACHMENT_MAX_BYTES,
  CASE_TEACHING_DOC_MAX_BYTES,
  CASE_UPLOAD_TOTAL_MAX_BYTES,
  SHOWCASE_DIRECT_FILE_UPLOADS_ENABLED,
  showcaseMaxMegabytes,
  isDiagramImageFile,
  isTeachingDocFile,
  isTemplateSourceFile,
  DIAGRAM_TYPE_OPTIONS,
  TAG_MAX_LENGTH,
  TAG_MAX_COUNT,
  type ShowcaseCaseType,
} from '@/components/showcase/showcaseShared'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useShowcaseMeta } from '@/composables/showcase/useShowcaseMeta'
import { processShowcaseGalleryImagePick } from '@/composables/showcase/processShowcaseGalleryImagePick'
import { usePublishShowcaseGalleryDrafts } from '@/composables/showcase/usePublishShowcaseGalleryDrafts'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'
import {
  cloneShowcaseDiagramSpec,
  decodeMgUploadSpec,
  inferDiagramTypeFromSpec,
} from '@/utils/showcaseDiagramThumbnail'
import { loadPublishShowcaseEditPost } from '@/composables/showcase/loadPublishShowcaseEditPost'
import { createPublishShowcaseSubmitHandlers } from '@/composables/showcase/submitPublishShowcasePost'
import { usePublishShowcaseAiOrchestration } from '@/composables/showcase/usePublishShowcaseAiOrchestration'

export type PublishShowcaseModalProps = {
  visible: boolean
  proxyMode?: boolean
  editPostId?: string | null
  diagramType?: string
  getDiagramSpec?: () => Record<string, unknown> | null
  getTitle?: () => string
  prepareForThumbnail?: () => Promise<void>
  getContainer?: () => HTMLElement | null
  restoreAfterThumbnail?: () => void
  defaultCaseType?: ShowcaseCaseType
}

export type PublishShowcaseModalEmit = {
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}

function isSessionExpiredMessage(message: string): boolean {
  return (
    message === 'SESSION_EXPIRED' ||
    /session expired|invalidated|login again|会话已过期|请重新登录/i.test(message)
  )
}

export function usePublishShowcaseModal(
  props: PublishShowcaseModalProps,
  emit: PublishShowcaseModalEmit,
) {
  const { t } = useLanguage()
  const notify = useNotifications()
  const { can } = useAdminAccess()
  const { subjectOptions, gradeOptions, recommendedTags: metaRecommendedTags } = useShowcaseMeta()
  const savedDiagramsStore = useSavedDiagramsStore()

  const uploadedMgSpec = ref<Record<string, unknown> | null>(null)
  const isMgSpecDecoding = ref(false)
  const isStep1Advancing = ref(false)
  const inlinePreviewRef = ref<{ captureThumbnail?: () => Promise<Blob | null> } | null>(null)

  const TITLE_MAX_LENGTH = 40

  const step = ref(1)
  const title = ref('')
  const description = ref('')
  const designHighlights = ref('')
  const tags = ref<string[]>([])
  const tagDraft = ref('')
  const caseType = ref<ShowcaseCaseType>('teaching_design')
  const subject = ref('')
  const grade = ref('')
  const diagramType = ref('')
  const teachingReflection = ref('')
  const classroomApplication = ref('')
  const isSubmitting = ref(false)
  const submitPhaseLabel = ref('')
  const isHistorySpecLoading = ref(false)
  const isGalleryImagesProcessing = ref(false)
  let galleryPickAbort: AbortController | null = null
  let publishSubmitAbort: AbortController | null = null
  const showHistoryPicker = ref(false)

  function abortPublishSubmit(): void {
    publishSubmitAbort?.abort()
    publishSubmitAbort = null
    if (isSubmitting.value) {
      isSubmitting.value = false
      submitPhaseLabel.value = ''
      notify.hideLoading()
    }
  }

  function releasePublishSubmit(): void {
    publishSubmitAbort = null
  }

  function beginPublishSubmit(): AbortSignal {
    abortPublishSubmit()
    publishSubmitAbort = new AbortController()
    return publishSubmitAbort.signal
  }

  const uploadedFile = ref<File | null>(null)
  const uploadedFileName = ref('')
  const attributionName = ref('')
  const attributionOrg = ref('')
  const autoApprove = ref(false)
  const selectedDiagram = ref<SavedDiagram | null>(null)
  const selectedDiagramSpec = ref<Record<string, unknown> | null>(null)
  const isEditLoading = ref(false)
  const editHasAttachment = ref(false)
  const editHasThumbnail = ref(false)

  const {
    galleryImageDrafts,
    galleryDiagramDrafts,
    galleryExistingImages,
    galleryTotalCount,
    galleryAtLimit,
    clearGalleryDrafts,
    newGalleryId,
    removeGalleryImageDraft,
    removeGalleryExistingImage,
    removeGalleryDiagramDraft,
    loadGalleryDiagramSpec,
    pushGalleryImageDraft,
    addGalleryDiagramDraft,
  } = usePublishShowcaseGalleryDrafts()

  const isEditMode = computed(() => Boolean(props.editPostId?.trim()))

  function isMgUploadedFile(file: File | null | undefined): boolean {
    return Boolean(file?.name.toLowerCase().endsWith('.mg'))
  }

  function hasTemplateStep1Source(): boolean {
    return Boolean(
      uploadedMgSpec.value ||
        selectedDiagram.value ||
        isMgUploadedFile(uploadedFile.value)
    )
  }

  function applyMgSpecToForm(spec: Record<string, unknown>): void {
    uploadedMgSpec.value = spec
    const inferred = inferDiagramTypeFromSpec(spec, diagramType.value || 'mind_map')
    if (!diagramType.value) {
      diagramType.value = inferred === 'mindmap' ? 'mind_map' : inferred
    }
  }

  async function ensureMgUploadSpecReady(): Promise<boolean> {
    if (uploadedMgSpec.value) return true
    const file = uploadedFile.value
    if (!isMgUploadedFile(file)) return false

    isMgSpecDecoding.value = true
    try {
      const spec = await decodeMgUploadSpec(file!)
      if (!spec) {
        notify.error(String(t('showcase.publishModal.invalidMgFile')))
        uploadedFile.value = null
        uploadedFileName.value = ''
        return false
      }
      applyMgSpecToForm(spec)
      return true
    } finally {
      isMgSpecDecoding.value = false
    }
  }

  const fromCanvas = computed(() => Boolean(props.getDiagramSpec) && !props.proxyMode)
  const canAutoApprove = computed(() => props.proxyMode && can('tab.showcase.edit'))
  const modalTitle = computed(() => {
    if (isEditMode.value) return String(t('showcase.publishModal.editTitle'))
    if (props.proxyMode) return String(t('admin.showcase.proxyFormTitle'))
    return String(t('showcase.publishModal.title'))
  })
  const submitButtonLabel = computed(() => {
    if (isSubmitting.value) {
      if (submitPhaseLabel.value) return submitPhaseLabel.value
      return String(
        t(
          isEditMode.value
            ? 'showcase.publishModal.resubmitting'
            : 'showcase.publishModal.submitting',
        ),
      )
    }
    return String(
      t(
        isEditMode.value
          ? 'showcase.publishModal.resubmit'
          : 'showcase.publishModal.submit',
      ),
    )
  })
  const isDiagramType = computed(
    () => caseType.value === 'diagram_case' || caseType.value === 'diagram_template'
  )

  const isDiagramTemplate = computed(() => caseType.value === 'diagram_template')
  const isDiagramCase = computed(() => caseType.value === 'diagram_case')
  /** Multi-item gallery publish UI for case + template (not teaching design). */
  const isDiagramGalleryCase = computed(
    () => caseType.value === 'diagram_case' || caseType.value === 'diagram_template'
  )

  const publishDiagramPreviewSpec = computed(() => {
    if (isDiagramGalleryCase.value) {
      const firstDiagram = galleryDiagramDrafts.value.find((entry) => entry.spec)
      return firstDiagram?.spec ?? uploadedMgSpec.value ?? selectedDiagramSpec.value
    }
    return null
  })

  const publishPreviewDiagramType = computed(() => {
    const fromSelected = selectedDiagram.value?.diagram_type
    const normalizedSelected = fromSelected === 'mindmap' ? 'mind_map' : fromSelected
    return (
      diagramType.value ||
      normalizedSelected ||
      (publishDiagramPreviewSpec.value
        ? inferDiagramTypeFromSpec(publishDiagramPreviewSpec.value, 'mind_map')
        : 'mind_map')
    )
  })

  const showPublishDiagramPreview = computed(() => Boolean(publishDiagramPreviewSpec.value))

  const diagramTypeFromHistory = computed(
    () => Boolean(selectedDiagram.value) || galleryDiagramDrafts.value.length > 0
  )

  const publishDiagramPreviewThumbnail = computed(
    () => selectedDiagram.value?.thumbnail ?? null
  )

  const subjectFilterOptions = computed(() => subjectOptions.value)
  const gradeFilterOptions = computed(() => gradeOptions.value)
  const diagramTypeFilterOptions = computed(() =>
    DIAGRAM_TYPE_OPTIONS.map((d) => ({ value: d.value, label: d.label }))
  )

  const tagsAtLimit = computed(() => tags.value.length >= TAG_MAX_COUNT)

  const recommendedTags = computed(() => {
    if (tagsAtLimit.value) return []
    const dynamic: string[] = []
    if (subject.value) dynamic.push(subject.value.slice(0, TAG_MAX_LENGTH))
    if (grade.value) dynamic.push(grade.value.slice(0, TAG_MAX_LENGTH))
    const merged = [...dynamic, ...metaRecommendedTags.value]
    return [...new Set(merged)].filter((t) => !tags.value.includes(t))
  })

  function pickRecommendedTag(tag: string) {
    tagDraft.value = tag.slice(0, TAG_MAX_LENGTH)
  }

  const step1Complete = computed(() => {
    if (props.proxyMode && !attributionName.value.trim()) return false
    if (!title.value.trim() || !subject.value || !grade.value) return false
    if (isDiagramType.value && !diagramType.value) return false
    if (fromCanvas.value) return true
    if (caseType.value === 'teaching_design') {
      return Boolean(uploadedFile.value || (isEditMode.value && editHasAttachment.value))
    }
    if (caseType.value === 'diagram_case') {
      return galleryTotalCount.value > 0
    }
    if (caseType.value === 'diagram_template') {
      return galleryTotalCount.value > 0 || hasTemplateStep1Source()
    }
    return Boolean(uploadedFile.value || selectedDiagram.value)
  })

  const currentStepTitle = computed(() =>
    step.value === 1
      ? String(t('showcase.publishModal.step1Title'))
      : String(t('showcase.publishModal.step2Title'))
  )

  const {
    isGenerating,
    aiGeneratePhase,
    clearAllAiPrefetch,
    resetAiCopyFields,
    generateDescription,
    markDescriptionDirty,
    markDesignHighlightsDirty,
    markClassroomApplicationDirty,
    beginStep2AiPrefetch,
  } = usePublishShowcaseAiOrchestration({
    t,
    notify,
    caseType,
    title,
    subject,
    grade,
    uploadedFile,
    description,
    designHighlights,
    classroomApplication,
    step,
    isDiagramType,
    fromCanvas,
    getDiagramSpec: props.getDiagramSpec,
    publishPreviewDiagramType,
    diagramType,
    uploadedMgSpec,
    selectedDiagramSpec,
    galleryDiagramDrafts,
    galleryImageDrafts,
    galleryExistingImages,
  })

  function resetForm() {
    clearAllAiPrefetch()
    step.value = 1
    title.value = ''
    description.value = ''
    designHighlights.value = ''
    tags.value = []
    tagDraft.value = ''
    caseType.value = 'teaching_design'
    subject.value = ''
    grade.value = ''
    diagramType.value = ''
    teachingReflection.value = ''
    classroomApplication.value = ''
    uploadedFile.value = null
    uploadedFileName.value = ''
    uploadedMgSpec.value = null
    attributionName.value = ''
    attributionOrg.value = ''
    autoApprove.value = false
    selectedDiagram.value = null
    selectedDiagramSpec.value = null
    editHasAttachment.value = false
    editHasThumbnail.value = false
    clearGalleryDrafts()
  }

  function abortGalleryImagePick(): void {
    galleryPickAbort?.abort()
    galleryPickAbort = null
    isGalleryImagesProcessing.value = false
  }

  watch(
    () => props.visible,
    (visible) => {
      if (!visible) {
        if (isSubmitting.value) {
          abortPublishSubmit()
        }
        abortGalleryImagePick()
        clearAllAiPrefetch()
        props.restoreAfterThumbnail?.()
        return
      }
      abortGalleryImagePick()
      resetForm()
      title.value = props.getTitle?.() || ''
      caseType.value = props.defaultCaseType || (props.getDiagramSpec ? 'diagram_case' : 'teaching_design')
      diagramType.value = props.diagramType || 'mind_map'
      if (props.editPostId?.trim()) {
        void loadPublishShowcaseEditPost(props.editPostId.trim(), {
          t, notify, emit, isEditLoading, title, description, tags, caseType, subject, grade,
          diagramType, teachingReflection, designHighlights, classroomApplication,
          editHasAttachment, editHasThumbnail, selectedDiagramSpec, uploadedFileName,
          galleryExistingImages, galleryDiagramDrafts, clearGalleryDrafts, newGalleryId,
          basenameFromMediaUrl,
        })
      } else {
        void warmHistoryDiagramCache()
      }
    }
  )

  async function warmHistoryDiagramCache(): Promise<void> {
    const loaded = await savedDiagramsStore.fetchDiagrams()
    if (!loaded) return
    void savedDiagramsStore.prefetchDiagramSpecs(savedDiagramsStore.diagrams.map((d) => d.id))
  }

  watch(caseType, (type) => {
    clearAllAiPrefetch()
    // Cross-type leftover gallery/file state must not satisfy step1 or steer submit.
    clearGalleryDrafts()
    selectedDiagram.value = null
    selectedDiagramSpec.value = null
    uploadedFile.value = null
    uploadedFileName.value = ''
    uploadedMgSpec.value = null
    if (type === 'teaching_design') {
      diagramType.value = ''
    } else if (!diagramType.value) {
      diagramType.value = props.diagramType || 'mind_map'
    }
  })

  function addTag() {
    const value = tagDraft.value.trim()
    if (!value) return
    if (tags.value.length >= TAG_MAX_COUNT) {
      notify.warning(String(t('showcase.publishModal.tagMaxCount', { max: TAG_MAX_COUNT })))
      return
    }
    if (!tags.value.includes(value)) {
      tags.value = [...tags.value, value.slice(0, TAG_MAX_LENGTH)]
    }
    tagDraft.value = ''
  }

  function removeTag(index: number) {
    tags.value = tags.value.filter((_, i) => i !== index)
  }

  function onTagKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault()
      addTag()
    }
  }

  function close() {
    if (isSubmitting.value) {
      abortPublishSubmit()
    }
    emit('update:visible', false)
  }

  function validateFile(file: File): boolean {
    if (caseType.value === 'teaching_design') return isTeachingDocFile(file.name)
    if (caseType.value === 'diagram_template') return isTemplateSourceFile(file.name)
    if (caseType.value === 'diagram_case') return isDiagramImageFile(file.name)
    return isTemplateSourceFile(file.name)
  }

  function galleryImageDraftsBytes(): number {
    return galleryImageDrafts.value.reduce((sum, draft) => sum + draft.file.size, 0)
  }

  function basenameFromMediaUrl(url: string): string {
    try {
      const path = new URL(url, window.location.origin).pathname
      const name = path.split('/').pop()
      return name && name.trim() ? name : url
    } catch {
      const name = url.split('/').pop()
      return name && name.trim() ? name : url
    }
  }

  function validateTeachingDocSize(file: File): boolean {
    if (caseType.value !== 'teaching_design') return true
    if (file.size <= CASE_TEACHING_DOC_MAX_BYTES) return true
    notify.error(
      String(
        t('showcase.publishModal.teachingDocTooLarge', {
          maxMb: showcaseMaxMegabytes(CASE_TEACHING_DOC_MAX_BYTES),
        })
      )
    )
    return false
  }

  async function onDiagramGalleryImagesInput(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement
    const files = input.files ? Array.from(input.files) : []
    input.value = ''
    if (!SHOWCASE_DIRECT_FILE_UPLOADS_ENABLED) {
      notify.info(String(t('showcase.publishModal.directUploadDisabled')))
      return
    }
    if (!files.length) return

    abortGalleryImagePick()
    const controller = new AbortController()
    galleryPickAbort = controller
    isGalleryImagesProcessing.value = true

    try {
      await processShowcaseGalleryImagePick({
        files,
        signal: controller.signal,
        maxPerFileBytes: CASE_ATTACHMENT_MAX_BYTES,
        maxTotalBytes: CASE_UPLOAD_TOTAL_MAX_BYTES,
        isImageFile: isDiagramImageFile,
        galleryAtLimit: () => galleryAtLimit.value,
        currentDraftBytes: galleryImageDraftsBytes,
        onEvent: (pickEvent) => {
          if (pickEvent.type === 'item') {
            pushGalleryImageDraft(pickEvent.processed)
            return
          }
          if (pickEvent.type !== 'reject') {
            return
          }
          if (pickEvent.reason === 'gallery_limit') {
            notify.error(
              String(t('showcase.publishModal.galleryLimit', { max: DIAGRAM_GALLERY_MAX_ITEMS }))
            )
            return
          }
          if (pickEvent.reason === 'invalid_type') {
            notify.error(String(t('showcase.publishModal.invalidFileType')))
            return
          }
          if (pickEvent.reason === 'too_large') {
            notify.error(
              String(
                t('showcase.publishModal.fileTooLarge', {
                  name: pickEvent.source.name,
                  maxMb: showcaseMaxMegabytes(CASE_ATTACHMENT_MAX_BYTES),
                })
              )
            )
            return
          }
          notify.error(String(t('showcase.publishModal.uploadTotalTooLarge')))
        },
      })
    } finally {
      if (galleryPickAbort === controller) {
        galleryPickAbort = null
        isGalleryImagesProcessing.value = false
      }
    }
  }

  async function addGalleryDiagram(diagram: SavedDiagram): Promise<void> {
    if (galleryDiagramDrafts.value.some((entry) => entry.diagram.id === diagram.id)) {
      notify.error(String(t('showcase.publishModal.galleryDuplicateDiagram')))
      return
    }
    if (galleryAtLimit.value) {
      notify.error(String(t('showcase.publishModal.galleryLimit', { max: DIAGRAM_GALLERY_MAX_ITEMS })))
      return
    }
    await addGalleryDiagramDraft(
      diagram,
      diagramType.value,
      (value) => {
        diagramType.value = value
      },
      diagramTypeFromSavedDiagram,
    )
  }

  function onFileInput(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (!SHOWCASE_DIRECT_FILE_UPLOADS_ENABLED) {
      notify.info(String(t('showcase.publishModal.directUploadDisabled')))
      return
    }
    if (!file) return
    if (!validateFile(file)) {
      notify.error(String(t('showcase.publishModal.invalidFileType')))
      return
    }
    if (!validateTeachingDocSize(file)) return
    clearAllAiPrefetch()
    uploadedFile.value = file
    uploadedFileName.value = file.name
    selectedDiagram.value = null
    selectedDiagramSpec.value = null
    uploadedMgSpec.value = null
    // New teaching doc: clear loaded/edit copy so step-2 prefetch can stream in.
    if (caseType.value === 'teaching_design') {
      resetAiCopyFields()
    }

    if (isMgUploadedFile(file)) {
      void ensureMgUploadSpecReady()
    }
  }

  function removeUploadedFile() {
    clearAllAiPrefetch()
    uploadedFile.value = null
    uploadedFileName.value = ''
    uploadedMgSpec.value = null
    selectedDiagram.value = null
    selectedDiagramSpec.value = null
    // Edit mode: clearing the chip means the prior attachment is no longer kept.
    if (caseType.value === 'teaching_design') {
      editHasAttachment.value = false
    }
  }

  function diagramTypeFromSavedDiagram(raw: string): string {
    return raw === 'mindmap' ? 'mind_map' : raw
  }

  function resolvePublishDiagramType(
    rawType: string,
    spec: Record<string, unknown>
  ): string {
    let type = diagramTypeFromSavedDiagram(rawType)
    if (!DIAGRAM_TYPE_OPTIONS.some((o) => o.value === type)) {
      type = inferDiagramTypeFromSpec(spec, 'mind_map')
    }
    if (!DIAGRAM_TYPE_OPTIONS.some((o) => o.value === type)) {
      return 'mind_map'
    }
    return type
  }

  function applyHistoryDiagramSpec(spec: Record<string, unknown>, diagram: SavedDiagram): boolean {
    try {
      selectedDiagramSpec.value = cloneShowcaseDiagramSpec(spec)
      diagramType.value = resolvePublishDiagramType(diagram.diagram_type, spec)
      return true
    } catch {
      selectedDiagramSpec.value = null
      return false
    }
  }

  async function ensureSelectedDiagramSpec(): Promise<boolean> {
    if (selectedDiagramSpec.value) return true
    if (!selectedDiagram.value) return false

    try {
      const cachedSpec = savedDiagramsStore.getCachedDiagramSpec(selectedDiagram.value.id)
      if (cachedSpec && applyHistoryDiagramSpec(cachedSpec, selectedDiagram.value)) {
        return true
      }

      isHistorySpecLoading.value = true
      const result = await savedDiagramsStore.getDiagram(selectedDiagram.value.id)
      if (result.ok && applyHistoryDiagramSpec(result.diagram.spec, selectedDiagram.value)) {
        return true
      }
      notify.error(String(t('showcase.publishModal.validationFile')))
      return false
    } catch {
      notify.error(String(t('showcase.publishModal.networkError')))
      return false
    } finally {
      isHistorySpecLoading.value = false
    }
  }

  async function onHistorySelect(diagram: SavedDiagram) {
    if (isDiagramGalleryCase.value) {
      await addGalleryDiagram(diagram)
      return
    }
    selectedDiagram.value = diagram
    uploadedFile.value = null
    uploadedFileName.value = diagram.title
    uploadedMgSpec.value = null
    diagramType.value = diagramTypeFromSavedDiagram(diagram.diagram_type) || 'mind_map'

    const cachedSpec = savedDiagramsStore.getCachedDiagramSpec(diagram.id)
    if (cachedSpec && applyHistoryDiagramSpec(cachedSpec, diagram)) {
      return
    }

    selectedDiagramSpec.value = null
    isHistorySpecLoading.value = true
    try {
      const result = await savedDiagramsStore.getDiagram(diagram.id)
      if (result.ok) {
        if (!applyHistoryDiagramSpec(result.diagram.spec, diagram)) {
          notify.error(String(t('showcase.publishModal.validationFile')))
        }
      } else {
        notify.error(String(t('showcase.publishModal.validationFile')))
      }
    } catch {
      notify.error(String(t('showcase.publishModal.networkError')))
    } finally {
      isHistorySpecLoading.value = false
    }
  }

  async function goNext() {
    if (props.proxyMode && !attributionName.value.trim()) {
      notify.error(String(t('admin.showcase.proxyAttributionRequired')))
      return
    }
    if (!title.value.trim()) {
      notify.error(String(t('showcase.publishModal.validationTitle')))
      return
    }
    if (!subject.value) {
      notify.error(String(t('showcase.publishModal.validationSubject')))
      return
    }
    if (!grade.value) {
      notify.error(String(t('showcase.publishModal.validationGrade')))
      return
    }
    if (isDiagramType.value && !diagramType.value) {
      notify.error(String(t('showcase.publishModal.validationDiagramType')))
      return
    }
    if (
      !fromCanvas.value &&
      caseType.value === 'teaching_design' &&
      !uploadedFile.value &&
      !(isEditMode.value && editHasAttachment.value)
    ) {
      notify.error(String(t('showcase.publishModal.validationFile')))
      return
    }
    isStep1Advancing.value = true
    try {
      if (!fromCanvas.value && isDiagramGalleryCase.value) {
        const needsLegacyTemplateSource =
          caseType.value === 'diagram_template' && galleryTotalCount.value < 1
        if (galleryTotalCount.value < 1 && !hasTemplateStep1Source()) {
          notify.error(String(t('showcase.publishModal.validationFile')))
          return
        }
        if (caseType.value === 'diagram_case' && galleryTotalCount.value < 1) {
          notify.error(String(t('showcase.publishModal.validationFile')))
          return
        }
        if (isMgUploadedFile(uploadedFile.value) && !uploadedMgSpec.value) {
          const mgReady = await ensureMgUploadSpecReady()
          if (!mgReady) return
        }
        if (galleryDiagramDrafts.value.some((draft) => !draft.spec)) {
          for (const draft of galleryDiagramDrafts.value) {
            if (!draft.spec && !(await loadGalleryDiagramSpec(draft))) {
              notify.error(String(t('showcase.publishModal.validationFile')))
              return
            }
          }
        }
        if (needsLegacyTemplateSource && selectedDiagram.value && !selectedDiagramSpec.value) {
          const specReady = await ensureSelectedDiagramSpec()
          if (!specReady) return
        }
      }
      step.value = 2
      beginStep2AiPrefetch()
    } finally {
      isStep1Advancing.value = false
    }
  }

  function goPrev() {
    clearAllAiPrefetch()
    step.value = 1
  }

  const { resolveThumbnail, submit } = createPublishShowcaseSubmitHandlers({
    props,
    emit,
    t,
    notify,
    can,
    isSubmitting,
    submitPhaseLabel,
    isEditMode,
    fromCanvas,
    title,
    description,
    tags,
    tagDraft,
    caseType,
    subject,
    grade,
    diagramType,
    teachingReflection,
    designHighlights,
    classroomApplication,
    attributionName,
    attributionOrg,
    autoApprove,
    uploadedFile,
    uploadedMgSpec,
    selectedDiagram,
    selectedDiagramSpec,
    editHasAttachment,
    editHasThumbnail,
    galleryImageDrafts,
    galleryDiagramDrafts,
    galleryExistingImages,
    galleryTotalCount,
    showPublishDiagramPreview,
    publishPreviewDiagramType,
    inlinePreviewRef,
    ensureSelectedDiagramSpec,
    ensureMgUploadSpecReady,
    isMgUploadedFile,
    loadGalleryDiagramSpec,
    resolvePublishDiagramType,
    resetForm,
    isSessionExpiredMessage,
    beginPublishSubmit,
    releasePublishSubmit,
  })

  const uploadAccept = computed(() => {
    if (caseType.value === 'teaching_design') return '.doc,.docx,.pdf,.pptx'
    if (caseType.value === 'diagram_template') return '.mg'
    if (caseType.value === 'diagram_case') return '.png,.jpg,.jpeg,.webp,.gif'
    return '.mg'
  })

  function caseTypeIcon(type: ShowcaseCaseType) {
    if (type === 'teaching_design') return BookOpen
    if (type === 'diagram_case') return ImageIcon
    return LayoutTemplate
  }

  return {
    uploadedMgSpec,
    isMgSpecDecoding,
    isStep1Advancing,
    inlinePreviewRef,
    TITLE_MAX_LENGTH,
    step,
    title,
    description,
    designHighlights,
    tags,
    tagDraft,
    caseType,
    subject,
    grade,
    diagramType,
    teachingReflection,
    classroomApplication,
    isSubmitting,
    isGenerating,
    aiGeneratePhase,
    isHistorySpecLoading,
    showHistoryPicker,
    uploadedFile,
    uploadedFileName,
    attributionName,
    attributionOrg,
    autoApprove,
    selectedDiagram,
    selectedDiagramSpec,
    isEditLoading,
    editHasAttachment,
    editHasThumbnail,
    galleryImageDrafts,
    galleryDiagramDrafts,
    galleryExistingImages,
    galleryTotalCount,
    galleryAtLimit,
    isGalleryImagesProcessing,
    isEditMode,
    fromCanvas,
    canAutoApprove,
    modalTitle,
    submitButtonLabel,
    isDiagramType,
    isDiagramTemplate,
    isDiagramCase,
    isDiagramGalleryCase,
    publishDiagramPreviewSpec,
    publishPreviewDiagramType,
    showPublishDiagramPreview,
    diagramTypeFromHistory,
    publishDiagramPreviewThumbnail,
    subjectFilterOptions,
    gradeFilterOptions,
    diagramTypeFilterOptions,
    tagsAtLimit,
    recommendedTags,
    step1Complete,
    currentStepTitle,
    uploadAccept,
    directFileUploadsEnabled: SHOWCASE_DIRECT_FILE_UPLOADS_ENABLED,
    pickRecommendedTag,
    addTag,
    removeTag,
    onTagKeydown,
    close,
    onDiagramGalleryImagesInput,
    removeGalleryImageDraft,
    removeGalleryExistingImage,
    removeGalleryDiagramDraft,
    onFileInput,
    removeUploadedFile,
    onHistorySelect,
    goNext,
    goPrev,
    generateDescription,
    markDescriptionDirty,
    markDesignHighlightsDirty,
    markClassroomApplicationDirty,
    submit,
    caseTypeIcon,
    CASE_TYPE_PUBLISH_OPTIONS,
    CASE_TEACHING_DOC_MAX_BYTES,
    showcaseMaxMegabytes,
    DIAGRAM_GALLERY_MAX_ITEMS,
    TAG_MAX_COUNT,
    TAG_MAX_LENGTH,
    t,
    X,
    Upload,
    History,
    Sparkles,
    BookOpen,
    ImageIcon,
    LayoutTemplate,
  }
}
