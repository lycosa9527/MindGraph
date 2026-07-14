/**
 * Load an existing Showcase post into the publish modal form.
 */
import type { Ref } from 'vue'

import {
  parseSpecGallery,
  type ShowcaseGalleryImageItem,
} from '@/components/showcase/showcaseGallery'
import type { ShowcaseCaseType } from '@/components/showcase/showcaseShared'
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type {
  GalleryDiagramDraft,
  GalleryExistingImage,
} from '@/composables/showcase/usePublishShowcaseGalleryDrafts'
import { getShowcasePost } from '@/utils/apiClient'
import { cloneShowcaseDiagramSpec } from '@/utils/showcaseDiagramThumbnail'

export type LoadEditPostDeps = {
  t: UseLanguageTranslate
  notify: {
    error: (message: string) => void
    warning: (message: string) => void
  }
  emit: {
    (e: 'update:visible', value: boolean): void
    (e: 'success'): void
  }
  isEditLoading: Ref<boolean>
  title: Ref<string>
  description: Ref<string>
  tags: Ref<string[]>
  caseType: Ref<ShowcaseCaseType>
  subject: Ref<string>
  grade: Ref<string>
  diagramType: Ref<string>
  teachingReflection: Ref<string>
  designHighlights: Ref<string>
  classroomApplication: Ref<string>
  editHasAttachment: Ref<boolean>
  editHasThumbnail: Ref<boolean>
  selectedDiagramSpec: Ref<Record<string, unknown> | null>
  uploadedFileName: Ref<string>
  galleryExistingImages: Ref<GalleryExistingImage[]>
  galleryDiagramDrafts: Ref<GalleryDiagramDraft[]>
  clearGalleryDrafts: () => void
  newGalleryId: () => string
  basenameFromMediaUrl: (url: string) => string
}

export async function loadPublishShowcaseEditPost(
  postId: string,
  deps: LoadEditPostDeps,
): Promise<void> {
  const {
    t,
    notify,
    emit,
    isEditLoading,
    title,
    description,
    tags,
    caseType,
    subject,
    grade,
    diagramType,
    teachingReflection,
    designHighlights,
    classroomApplication,
    editHasAttachment,
    editHasThumbnail,
    selectedDiagramSpec,
    uploadedFileName,
    galleryExistingImages,
    galleryDiagramDrafts,
    clearGalleryDrafts,
    newGalleryId,
    basenameFromMediaUrl,
  } = deps


  isEditLoading.value = true
  try {
    const loaded = await getShowcasePost(postId)
    if (!loaded.can_resubmit && !loaded.can_edit) {
      notify.error(String(t('showcase.detail.loadFailed')))
      emit('update:visible', false)
      return
    }
    title.value = loaded.title
    description.value = loaded.description ?? ''
    tags.value = [...(loaded.tags ?? [])]
    caseType.value = loaded.case_type
    subject.value = loaded.subject ?? ''
    grade.value = loaded.grade ?? ''
    diagramType.value = loaded.diagram_type ?? ''
    editHasAttachment.value = Boolean(loaded.attachment_url)
    editHasThumbnail.value = Boolean(loaded.thumbnail_url)

    const spec = (loaded as { spec?: Record<string, unknown> }).spec
    if (spec && typeof spec === 'object') {
      if (typeof spec.teaching_reflection === 'string') {
        teachingReflection.value = spec.teaching_reflection
      }
      if (typeof spec.design_highlights === 'string') {
        designHighlights.value = spec.design_highlights
      } else if (Array.isArray(spec.design_highlights)) {
        designHighlights.value = spec.design_highlights.map((item) => String(item)).join('\n')
      }
      if (typeof spec.classroom_application === 'string') {
        classroomApplication.value = spec.classroom_application
      }
      if (loaded.case_type !== 'teaching_design') {
        selectedDiagramSpec.value = null
        clearGalleryDrafts()
        if (loaded.gallery_items?.length) {
          for (const item of loaded.gallery_items) {
            if (item.kind === 'image' && item.url) {
              const imageEntry = parseSpecGallery(spec).find(
                (entry): entry is ShowcaseGalleryImageItem =>
                  entry.kind === 'image' && entry.filename === item.filename
              )
              const path = imageEntry?.path
              galleryExistingImages.value.push({
                path: path ?? item.url.replace(/^\/static\//, ''),
                filename: item.filename ?? 'image',
                url: item.url,
              })
            } else if (item.kind === 'diagram' && item.diagram_id) {
              galleryDiagramDrafts.value.push({
                id: newGalleryId(),
                diagram: {
                  id: item.diagram_id,
                  title: item.title ?? item.diagram_id,
                  diagram_type: item.diagram_type ?? loaded.diagram_type ?? 'mind_map',
                  thumbnail: null,
                  updated_at: loaded.created_at,
                  is_pinned: false,
                },
                spec: item.spec ? cloneShowcaseDiagramSpec(item.spec) : null,
                title: item.title ?? item.diagram_id,
              })
            }
          }
        } else if (spec && typeof spec === 'object') {
          const gallery = parseSpecGallery(spec)
          if (gallery.length > 0) {
            const missingImages = gallery.filter((entry) => entry.kind === 'image' && !entry.path).length
            if (missingImages > 0) {
              notify.warning(String(t('showcase.publishModal.galleryReuploadHint')))
            }
            for (const entry of gallery) {
              if (entry.kind === 'image' && entry.path) {
                galleryExistingImages.value.push({
                  path: entry.path,
                  filename: entry.filename,
                  url: `/static/${entry.path.replace(/^\/+/, '')}`,
                })
              } else if (entry.kind === 'diagram') {
                galleryDiagramDrafts.value.push({
                  id: newGalleryId(),
                  diagram: {
                    id: entry.diagram_id,
                    title: entry.title,
                    diagram_type: entry.diagram_type ?? loaded.diagram_type ?? 'mind_map',
                    thumbnail: null,
                    updated_at: loaded.created_at,
                    is_pinned: false,
                  },
                  spec: entry.spec ? cloneShowcaseDiagramSpec(entry.spec) : null,
                  title: entry.title,
                })
              }
            }
          } else if (spec.source === 'image_upload' && typeof spec.source_file_path === 'string') {
            galleryExistingImages.value.push({
              path: spec.source_file_path,
              filename: basenameFromMediaUrl(loaded.source_file_url ?? spec.source_file_path),
              url: loaded.source_file_url ?? `/static/${spec.source_file_path.replace(/^\/+/, '')}`,
            })
          } else if (spec.topic || spec.nodes || spec.children || spec.center) {
            galleryDiagramDrafts.value.push({
              id: newGalleryId(),
              diagram: {
                id: String(spec.source_diagram_id ?? loaded.id),
                title: loaded.title,
                diagram_type: loaded.diagram_type ?? 'mind_map',
                thumbnail: loaded.thumbnail_url,
                updated_at: loaded.created_at,
                is_pinned: false,
              },
              spec: cloneShowcaseDiagramSpec(spec),
              title: loaded.title,
            })
          }
        }
      }
      if (typeof spec?.attachment_filename === 'string') {
        uploadedFileName.value = spec.attachment_filename
      }
    }
  } catch (e) {
    notify.error(e instanceof Error ? e.message : String(t('showcase.detail.loadFailed')))
    emit('update:visible', false)
  } finally {
    isEditLoading.value = false
  }
}
