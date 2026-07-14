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
  CASE_ATTACHMENT_MAX_BYTES,
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
import { captureTeachingDocThumbnail } from '@/utils/captureTeachingDocThumbnail'

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
    error: (message: string) => void
    success: (message: string, duration?: number) => void
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
  ): Promise<void> {
    const total = pending.length
    for (let index = 0; index < total; index += 1) {
      const item = pending[index]
      if (!item) continue
      setSubmitProgress(
        String(
          t('showcase.publishModal.uploadingFile', {
            name: displayNameForUpload(item),
            current: index + 1,
            total,
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
  }

  async function rollbackCreatedPost(postId: string, proxyMode: boolean): Promise<void> {
    try {
      // Pending author posts use withdraw (hard-delete + asset cleanup)
      await withdrawShowcasePost(postId)
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
  ): Promise<string> {
    const proxyMode = options.proxyMode === true
    const approveAfterUpload = options.approveAfterUpload === true
    setSubmitProgress(String(t('showcase.publishModal.creatingCase')))
    const result = await createFn()
    const postId = result.post.id
    if (pending.length === 0) {
      setSubmitProgress(String(t('showcase.publishModal.finishing')))
      return postId
    }
    try {
      await uploadPendingMedia(postId, pending)
      if (approveAfterUpload) {
        setSubmitProgress(String(t('showcase.publishModal.finishing')))
        await reviewAdminShowcasePost(postId, 'approve')
      }
      setSubmitProgress(String(t('showcase.publishModal.finishing')))
    } catch {
      await rollbackCreatedPost(postId, proxyMode)
      throw new Error('SHOWCASE_UPLOAD_ROLLED_BACK')
    }
    return postId
  }

  function mapSubmitError(error: unknown): string {
    const message = error instanceof Error ? error.message : ''
    if (isSessionExpiredMessage(message)) {
      return String(t('auth.sessionExpired'))
    }
    if (message === 'SHOWCASE_UPLOAD_ROLLED_BACK') {
      return String(t('showcase.publishModal.uploadFailedRolledBack'))
    }
    if (
      message === 'NETWORK_ERROR' ||
      message === 'Failed to fetch' ||
      /network|fetch failed/i.test(message)
    ) {
      return String(t('showcase.publishModal.networkError'))
    }
    if (
      message.startsWith('SHOWCASE_STORAGE_PUT_FAILED') ||
      /Upload to storage failed|upload failed|presigned|COS|storage/i.test(message)
    ) {
      return String(t('showcase.publishModal.uploadFailed'))
    }
    return message || String(t('showcase.publishModal.uploadFailed'))
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
        const teachingThumb = uploadedFile.value
          ? await captureTeachingDocThumbnail(uploadedFile.value)
          : null
        if (teachingThumb) {
          pendingUploads.push({
            role: 'thumbnail',
            file: blobToPngFile(teachingThumb),
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

          const thumb = await resolveThumbnail()
          if (thumb) {
            pendingUploads.push({ role: 'thumbnail', file: blobToPngFile(thumb) })
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

          const thumb = await resolveThumbnail()
          if (thumb) {
            pendingUploads.push({ role: 'thumbnail', file: blobToPngFile(thumb) })
          }
        }
      }

      let savedPostId = props.editPostId?.trim() ?? ''
      if (props.proxyMode) {
        const canAutoApprove = autoApprove.value && can('tab.showcase.edit')
        const approveAfterUpload = canAutoApprove && pendingUploads.length > 0
        if (canAutoApprove && pendingUploads.length === 0) {
          formData.append('auto_approve', 'true')
        }
        savedPostId = await createThenUpload(
          () => proxyCreateShowcasePost(formData),
          pendingUploads,
          { proxyMode: true, approveAfterUpload },
        )
        clearSubmitProgress()
        notify.success(String(t('admin.showcase.proxySuccess')), 3000)
        showcaseStore.emitAdminUpdated()
      } else if (isEditMode.value && savedPostId) {
        setSubmitProgress(String(t('showcase.publishModal.submitting')))
        await updateShowcasePost(savedPostId, formData)
        if (pendingUploads.length > 0) {
          await uploadPendingMedia(savedPostId, pendingUploads)
        }
        setSubmitProgress(String(t('showcase.publishModal.finishing')))
        clearSubmitProgress()
        notify.success(String(t('showcase.resubmitted')), 3000)
        showcaseStore.emitPostUpdated(savedPostId)
        showcaseStore.emitFeedInvalidate('resubmit')
      } else {
        savedPostId = await createThenUpload(
          () => createShowcasePost(formData),
          pendingUploads,
        )
        clearSubmitProgress()
        notify.success(String(t('showcase.publishModal.success')), 3000)
        showcaseStore.emitFeedInvalidate('publish')
      }
      emit('update:visible', false)
      emit('success')
      resetForm()
    } catch (e) {
      clearSubmitProgress()
      notify.error(mapSubmitError(e))
    } finally {
      clearSubmitProgress()
      isSubmitting.value = false
    }
  }

  return { resolveThumbnail, submit }
}
