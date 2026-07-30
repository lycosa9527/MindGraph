/**
 * Thumbnail resolve + submit handlers for the Showcase publish modal.
 * Flow: create/update metadata → init → PUT (or local complete) → complete.
 */
import { type Ref } from 'vue'

import {
  buildGallerySpecPayload,
  type ShowcaseGalleryItem,
} from '@/components/showcase/showcaseGallery'
import {
  acceptThumbnailBlob,
  CASE_ATTACHMENT_MAX_BYTES,
  CASE_THUMBNAIL_MAX_BYTES,
  CASE_UPLOAD_TOTAL_MAX_BYTES,
  CASE_VIDEO_MAX_BYTES,
  TAG_MAX_COUNT,
  TAG_MAX_LENGTH,
  type ShowcaseCaseType,
} from '@/components/showcase/showcaseShared'
import type { AdminCapability } from '@/utils/adminCapabilities'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import {
  uploadShowcaseFile,
  type ShowcaseUploadRole,
} from '@/composables/showcase/uploadShowcaseFile'
import { mapShowcaseSubmitError } from '@/composables/showcase/mapShowcaseSubmitError'
import { resolvePublishThumbnail } from '@/composables/showcase/publishShowcaseThumbnails'
import type {
  GalleryDiagramDraft,
  GalleryExistingImage,
  GalleryImageDraft,
} from '@/composables/showcase/usePublishShowcaseGalleryDrafts'
import type { SavedDiagram } from '@/stores/savedDiagrams'
import { useShowcaseStore } from '@/stores/showcase'
import {
  createShowcasePost,
  deleteAdminShowcasePost,
  proxyCreateShowcasePost,
  reviewAdminShowcasePost,
  updateShowcasePost,
  withdrawShowcasePost,
} from '@/utils/apiClient'
import {
  cloneShowcaseDiagramSpec,
  inferDiagramTypeFromSpec,
} from '@/utils/showcaseDiagramThumbnail'

export type PublishSubmitDeps = {
  props: {
    proxyMode?: boolean
    editPostId?: string | null
    getDiagramSpec?: () => Record<string, unknown> | null
    getContainer?: () => HTMLElement | null
    prepareForThumbnail?: () => Promise<void>
  }
  emit: {
    (e: 'update:visible', value: boolean): void
    (e: 'success'): void
  }
  t: UseLanguageTranslate
  notify: {
    error: (message: string, duration?: number) => void
    success: (message: string, duration?: number) => void
    warning: (message: string, duration?: number) => void
    info: (message: string, duration?: number) => void
    showLoading: (message?: string) => void
    hideLoading: () => void
  }
  can: (cap: AdminCapability) => boolean
  isSubmitting: Ref<boolean>
  submitPhaseLabel: Ref<string>
  isEditMode: { value: boolean }
  fromCanvas: { value: boolean }
  title: Ref<string>
  description: Ref<string>
  tags: Ref<string[]>
  tagDraft: Ref<string>
  caseType: Ref<ShowcaseCaseType>
  subject: Ref<string>
  grade: Ref<string>
  diagramType: Ref<string>
  teachingReflection: Ref<string>
  designHighlights: Ref<string>
  classroomApplication: Ref<string>
  attributionName: Ref<string>
  attributionOrg: Ref<string>
  autoApprove: Ref<boolean>
  uploadedFile: Ref<File | null>
  uploadedMgSpec: Ref<Record<string, unknown> | null>
  selectedDiagram: Ref<SavedDiagram | null>
  selectedDiagramSpec: Ref<Record<string, unknown> | null>
  editHasAttachment: Ref<boolean>
  editHasThumbnail: Ref<boolean>
  galleryImageDrafts: Ref<GalleryImageDraft[]>
  galleryDiagramDrafts: Ref<GalleryDiagramDraft[]>
  galleryExistingImages: Ref<GalleryExistingImage[]>
  galleryTotalCount: { value: number }
  showPublishDiagramPreview: { value: boolean }
  publishPreviewDiagramType: { value: string }
  inlinePreviewRef: Ref<{ captureThumbnail?: () => Promise<Blob | null> } | null>
  thumbnailCaptureHost: Ref<HTMLElement | null>
  showThumbnailCapture: Ref<boolean>
  ensureSelectedDiagramSpec: () => Promise<boolean>
  ensureMgUploadSpecReady: () => Promise<boolean>
  isMgUploadedFile: (file: File | null | undefined) => boolean
  loadGalleryDiagramSpec: (draft: GalleryDiagramDraft) => Promise<boolean>
  resolvePublishDiagramType: (raw: string, spec: Record<string, unknown>) => string
  resetForm: () => void
  isSessionExpiredMessage: (message: string) => boolean
}

function blobToPngFile(blob: Blob, name = 'thumbnail.png'): File {
  return new File([blob], name, { type: 'image/png' })
}

async function prepareThumbnailUploadFile(blob: Blob | null): Promise<File | null> {
  const prepared = await acceptThumbnailBlob(blob)
  if (!prepared || prepared.size > CASE_THUMBNAIL_MAX_BYTES) return null
  return blobToPngFile(prepared)
}

function isThumbnailUploadRole(role: ShowcaseUploadRole): boolean {
  return role === 'thumbnail'
}

function coverSkipKeyForCase(caseTypeValue: ShowcaseCaseType): string {
  if (caseTypeValue === 'diagram_template') {
    return 'showcase.publishModal.cannotPreviewTemplate'
  }
  return 'showcase.publishModal.cannotPreview'
}

export function createPublishShowcaseSubmitHandlers(deps: PublishSubmitDeps) {
  const {
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
    thumbnailCaptureHost,
    showThumbnailCapture,
    ensureSelectedDiagramSpec,
    ensureMgUploadSpecReady,
    isMgUploadedFile,
    loadGalleryDiagramSpec,
    resolvePublishDiagramType,
    resetForm,
    isSessionExpiredMessage,
  } = deps

  const showcaseStore = useShowcaseStore()

  function setSubmitProgress(message: string): void {
    submitPhaseLabel.value = message
    notify.showLoading(message)
  }

  function clearSubmitProgress(): void {
    submitPhaseLabel.value = ''
    notify.hideLoading()
  }

  function displayNameForUpload(item: {
    role: ShowcaseUploadRole
    file: File
    filename?: string
  }): string {
    return item.filename || item.file.name || String(item.role)
  }

  async function resolveThumbnail(): Promise<Blob | null> {
    return resolvePublishThumbnail({
      fromCanvas: fromCanvas.value,
      props,
      galleryImageDrafts: galleryImageDrafts.value,
      uploadedFile: uploadedFile.value,
      showPublishDiagramPreview: showPublishDiagramPreview.value,
      inlinePreviewRef,
      uploadedMgSpec: uploadedMgSpec.value,
      selectedDiagramSpec: selectedDiagramSpec.value,
      selectedDiagram: selectedDiagram.value,
      publishPreviewDiagramType: publishPreviewDiagramType.value,
      thumbnailCaptureHost,
      showThumbnailCapture,
    })
  }

  function buildSpecExtras(): Record<string, unknown> {
    const extras: Record<string, unknown> = {}
    if (caseType.value === 'teaching_design') {
      extras.type = 'teaching_design'
      if (teachingReflection.value.trim()) {
        extras.teaching_reflection = teachingReflection.value.trim()
      }
      if (designHighlights.value.trim()) {
        extras.design_highlights = designHighlights.value.trim()
      }
    } else if (classroomApplication.value.trim()) {
      extras.classroom_application = classroomApplication.value.trim()
    }
    if (selectedDiagram.value && caseType.value !== 'diagram_case') {
      extras.source_diagram_id = selectedDiagram.value.id
    }
    return extras
  }

  function validateUploadSizes(): string | null {
    const files: File[] = []
    if (uploadedFile.value) files.push(uploadedFile.value)
    for (const draft of galleryImageDrafts.value) {
      files.push(draft.file)
    }

    let total = 0
    for (const file of files) {
      const isVideo = file.type.startsWith('video/')
      const max = isVideo ? CASE_VIDEO_MAX_BYTES : CASE_ATTACHMENT_MAX_BYTES
      if (file.size > max) {
        const maxMb = Math.round(max / 1024 / 1024)
        return String(t('showcase.publishModal.fileTooLarge', { name: file.name, maxMb }))
      }
      total += file.size
    }
    if (total > CASE_UPLOAD_TOTAL_MAX_BYTES) {
      return String(t('showcase.publishModal.uploadTotalTooLarge'))
    }
    return null
  }

  async function uploadPendingMedia(
    postId: string,
    pending: Array<{ role: ShowcaseUploadRole; file: File; filename?: string }>,
  ): Promise<{ coverUploadFailed: boolean }> {
    const required = pending.filter((item) => !isThumbnailUploadRole(item.role))
    const covers = pending.filter((item) => isThumbnailUploadRole(item.role))
    const total = required.length + covers.length
    let uploaded = 0

    for (const item of required) {
      uploaded += 1
      setSubmitProgress(
        String(
          t('showcase.publishModal.uploadingFile', {
            name: displayNameForUpload(item),
            current: uploaded,
            total: Math.max(total, 1),
          }),
        ),
      )
      await uploadShowcaseFile({
        postId,
        role: item.role,
        file: item.file,
        filename: item.filename,
      })
    }

    let coverUploadFailed = false
    for (const item of covers) {
      uploaded += 1
      setSubmitProgress(
        String(
          t('showcase.publishModal.uploadingFile', {
            name: displayNameForUpload(item),
            current: uploaded,
            total: Math.max(total, 1),
          }),
        ),
      )
      try {
        await uploadShowcaseFile({
          postId,
          role: item.role,
          file: item.file,
          filename: item.filename,
        })
      } catch (coverError) {
        // Keep attachment/gallery/source; cover is best-effort for card display.
        console.warn('[Showcase] cover upload soft-failed', postId, coverError)
        coverUploadFailed = true
      }
    }
    return { coverUploadFailed }
  }

  function uploadFailureReason(error: unknown): string {
    if (error instanceof Error && error.message.trim()) {
      return `upload_${error.message.trim()}`.slice(0, 200)
    }
    return 'upload_failed'
  }

  async function rollbackCreatedPost(
    postId: string,
    proxyMode: boolean,
    reason: string,
  ): Promise<void> {
    try {
      // Pending author posts use withdraw (hard-delete + asset cleanup)
      await withdrawShowcasePost(postId, { reason })
    } catch {
      if (!proxyMode) {
        return
      }
      try {
        // Auto-approved / staff proxy posts cannot be withdrawn by author rules
        await deleteAdminShowcasePost(postId)
      } catch {
        // Best-effort: leave orphan for author/admin cleanup
      }
    }
  }

  async function createThenUpload(
    createFn: () => Promise<{ post: { id: string } }>,
    pending: Array<{ role: ShowcaseUploadRole; file: File; filename?: string }>,
    options: { proxyMode?: boolean; approveAfterUpload?: boolean } = {},
  ): Promise<{ postId: string; coverUploadFailed: boolean }> {
    const proxyMode = options.proxyMode === true
    const approveAfterUpload = options.approveAfterUpload === true
    setSubmitProgress(String(t('showcase.publishModal.creatingCase')))
    const result = await createFn()
    const postId = result.post.id
    if (pending.length === 0) {
      setSubmitProgress(String(t('showcase.publishModal.finishing')))
      return { postId, coverUploadFailed: false }
    }
    try {
      const { coverUploadFailed } = await uploadPendingMedia(postId, pending)
      if (approveAfterUpload) {
        setSubmitProgress(String(t('showcase.publishModal.finishing')))
        await reviewAdminShowcasePost(postId, 'approve')
      }
      setSubmitProgress(String(t('showcase.publishModal.finishing')))
      return { postId, coverUploadFailed }
    } catch (uploadError) {
      const cause =
        uploadError instanceof Error && uploadError.message.trim()
          ? uploadError.message.trim()
          : 'upload_failed'
      console.error('[Showcase] upload failed; rolling back draft', postId, uploadError)
      await rollbackCreatedPost(postId, proxyMode, uploadFailureReason(uploadError))
      throw new Error(`SHOWCASE_UPLOAD_ROLLED_BACK:${cause}`)
    }
  }

  function mapSubmitError(error: unknown): string {
    return mapShowcaseSubmitError(error, t, isSessionExpiredMessage)
  }

  async function submit() {
    if (isSubmitting.value) return
    isSubmitting.value = true
    try {
      const sizeError = validateUploadSizes()
      if (sizeError) {
        notify.error(sizeError)
        return
      }
      const formTags = [...tags.value]
      if (tagDraft.value.trim() && formTags.length < TAG_MAX_COUNT) {
        const draft = tagDraft.value.trim()
        if (!formTags.includes(draft)) formTags.push(draft.slice(0, TAG_MAX_LENGTH))
      }

      const formData = new FormData()
      const pendingUploads: Array<{ role: ShowcaseUploadRole; file: File; filename?: string }> = []

      formData.append('title', title.value.trim())
      formData.append('description', description.value.trim())
      formData.append('tags', JSON.stringify(formTags))
      formData.append('case_type', caseType.value)
      formData.append('subject', subject.value)
      formData.append('grade', grade.value)

      if (teachingReflection.value.trim()) {
        formData.append('teaching_reflection', teachingReflection.value.trim())
      }
      if (designHighlights.value.trim()) {
        formData.append('design_highlights', designHighlights.value.trim())
      }
      if (classroomApplication.value.trim()) {
        formData.append('classroom_application', classroomApplication.value.trim())
      }

      if (props.proxyMode) {
        formData.append('attribution_name', attributionName.value.trim())
        formData.append('attribution_org', attributionOrg.value.trim())
      }

      let coverSkipKey: string | null = null

      if (caseType.value === 'teaching_design') {
        if (!uploadedFile.value && !(isEditMode.value && editHasAttachment.value)) {
          notify.error(String(t('showcase.publishModal.validationFile')))
          return
        }
        if (uploadedFile.value) {
          pendingUploads.push({
            role: 'attachment',
            file: uploadedFile.value,
            filename: uploadedFile.value.name,
          })
        }
      } else {
        if (caseType.value === 'diagram_template' && selectedDiagram.value && !selectedDiagramSpec.value) {
          const specReady = await ensureSelectedDiagramSpec()
          if (!specReady) return
        }
        if (caseType.value === 'diagram_template' && isMgUploadedFile(uploadedFile.value) && !uploadedMgSpec.value) {
          const mgReady = await ensureMgUploadSpecReady()
          if (!mgReady) return
        }
        if (uploadedMgSpec.value && !diagramType.value) {
          const inferred = inferDiagramTypeFromSpec(uploadedMgSpec.value, 'mind_map')
          diagramType.value = inferred === 'mindmap' ? 'mind_map' : inferred
        }

        formData.append('diagram_type', diagramType.value)

        if (caseType.value === 'diagram_case' && !fromCanvas.value) {
          if (galleryTotalCount.value < 1) {
            notify.error(String(t('showcase.publishModal.validationFile')))
            return
          }
          for (const draft of galleryDiagramDrafts.value) {
            if (!(await loadGalleryDiagramSpec(draft))) {
              notify.error(String(t('showcase.publishModal.validationFile')))
              return
            }
          }
          const galleryItems: ShowcaseGalleryItem[] = []
          for (const existing of galleryExistingImages.value) {
            galleryItems.push({
              kind: 'image',
              path: existing.path,
              filename: existing.filename,
            })
          }
          for (const img of galleryImageDrafts.value) {
            galleryItems.push({ kind: 'image', filename: img.filename, pending: true })
          }
          for (const draft of galleryDiagramDrafts.value) {
            galleryItems.push({
              kind: 'diagram',
              diagram_id: draft.diagram.id,
              title: draft.title,
              diagram_type: resolvePublishDiagramType(draft.diagram.diagram_type, draft.spec!),
              spec: cloneShowcaseDiagramSpec(draft.spec!),
            })
          }
          const specObj: Record<string, unknown> = {
            type: 'diagram_case',
            source: 'gallery',
            gallery: buildGallerySpecPayload(galleryItems),
          }
          if (classroomApplication.value.trim()) {
            specObj.classroom_application = classroomApplication.value.trim()
          }
          formData.append('spec', JSON.stringify(specObj))

          // Match pending image slots to gallery indices
          let imageDraftIdx = 0
          const payloadGallery = buildGallerySpecPayload(galleryItems)
          for (let slot = 0; slot < payloadGallery.length; slot += 1) {
            const item = payloadGallery[slot]
            if (item.kind !== 'image' || !item.pending) continue
            const draft = galleryImageDrafts.value[imageDraftIdx]
            imageDraftIdx += 1
            if (!draft) continue
            pendingUploads.push({
              role: `gallery_${slot}` as ShowcaseUploadRole,
              file: draft.file,
              filename: draft.filename,
            })
          }

          const thumbFile = await prepareThumbnailUploadFile(await resolveThumbnail())
          if (thumbFile) {
            pendingUploads.push({ role: 'thumbnail', file: thumbFile })
          } else if (!(isEditMode.value && editHasThumbnail.value)) {
            coverSkipKey = coverSkipKeyForCase(caseType.value)
          }
        } else {
          let specObj: Record<string, unknown> | null = null

          if (fromCanvas.value) {
            specObj = props.getDiagramSpec?.() ?? null
          } else if (selectedDiagramSpec.value) {
            specObj = cloneShowcaseDiagramSpec(selectedDiagramSpec.value)
          } else if (uploadedMgSpec.value) {
            specObj = cloneShowcaseDiagramSpec(uploadedMgSpec.value)
            if (uploadedFile.value) {
              pendingUploads.push({
                role: 'source',
                file: uploadedFile.value,
                filename: uploadedFile.value.name,
              })
            }
          } else if (caseType.value === 'diagram_template') {
            notify.error(String(t('showcase.publishModal.validationFile')))
            return
          } else if (uploadedFile.value?.name.toLowerCase().endsWith('.mg')) {
            notify.error(String(t('showcase.publishModal.invalidMgFile')))
            return
          } else {
            specObj = { type: caseType.value, source: 'image_upload' }
          }

          if (!specObj) {
            if (isEditMode.value && selectedDiagramSpec.value) {
              specObj = cloneShowcaseDiagramSpec(selectedDiagramSpec.value)
            } else {
              notify.error(String(t('community.shareModal.noDiagramData')))
              return
            }
          }

          Object.assign(specObj, buildSpecExtras())
          formData.append('spec', JSON.stringify(specObj))

          if (
            uploadedFile.value &&
            !uploadedFile.value.name.toLowerCase().endsWith('.mg') &&
            !pendingUploads.some((u) => u.role === 'source')
          ) {
            pendingUploads.push({
              role: 'source',
              file: uploadedFile.value,
              filename: uploadedFile.value.name,
            })
          }

          const thumbFile = await prepareThumbnailUploadFile(await resolveThumbnail())
          if (thumbFile) {
            pendingUploads.push({ role: 'thumbnail', file: thumbFile })
          } else if (!(isEditMode.value && editHasThumbnail.value)) {
            coverSkipKey = coverSkipKeyForCase(caseType.value)
          }
        }
      }

      let coverUploadFailed = false
      let savedPostId = props.editPostId?.trim() ?? ''
      const teachingDesignAttachmentUploaded =
        caseType.value === 'teaching_design' &&
        pendingUploads.some((u) => u.role === 'attachment')
      if (props.proxyMode) {
        const canAutoApprove = autoApprove.value && can('tab.showcase.edit')
        const approveAfterUpload = canAutoApprove && pendingUploads.length > 0
        if (canAutoApprove && pendingUploads.length === 0) {
          formData.append('auto_approve', 'true')
        }
        const created = await createThenUpload(
          () => proxyCreateShowcasePost(formData),
          pendingUploads,
          { proxyMode: true, approveAfterUpload },
        )
        savedPostId = created.postId
        coverUploadFailed = created.coverUploadFailed
        clearSubmitProgress()
        notify.success(String(t('admin.showcase.proxySuccess')), 3000)
        showcaseStore.emitAdminUpdated()
      } else if (isEditMode.value && savedPostId) {
        setSubmitProgress(String(t('showcase.publishModal.submitting')))
        await updateShowcasePost(savedPostId, formData)
        if (pendingUploads.length > 0) {
          const uploaded = await uploadPendingMedia(savedPostId, pendingUploads)
          coverUploadFailed = uploaded.coverUploadFailed
        }
        setSubmitProgress(String(t('showcase.publishModal.finishing')))
        clearSubmitProgress()
        notify.success(String(t('showcase.resubmitted')), 3000)
        showcaseStore.emitPostUpdated(savedPostId)
        showcaseStore.emitFeedInvalidate('resubmit')
      } else {
        const created = await createThenUpload(
          () => createShowcasePost(formData),
          pendingUploads,
        )
        savedPostId = created.postId
        coverUploadFailed = created.coverUploadFailed
        clearSubmitProgress()
        notify.success(String(t('showcase.publishModal.success')), 3000)
        showcaseStore.emitFeedInvalidate('publish')
      }
      if (teachingDesignAttachmentUploaded && savedPostId) {
        showcaseStore.markCoverPending(savedPostId)
        notify.info(String(t('showcase.publishModal.coverGenerating')), 5000)
      } else if (coverUploadFailed) {
        notify.warning(String(t('showcase.publishModal.coverUploadSkipped')), 8000)
      } else if (coverSkipKey) {
        notify.warning(String(t(coverSkipKey)), 8000)
      }
      emit('update:visible', false)
      emit('success')
      resetForm()
    } catch (e) {
      clearSubmitProgress()
      // Longer duration — upload failures are easy to miss after the loading toast closes
      notify.error(mapSubmitError(e), 10000)
    } finally {
      clearSubmitProgress()
      isSubmitting.value = false
    }
  }

  return { resolveThumbnail, submit }
}
