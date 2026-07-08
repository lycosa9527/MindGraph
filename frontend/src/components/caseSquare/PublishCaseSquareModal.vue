<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { BookOpen, History, Image as ImageIcon, LayoutTemplate, Sparkles, Upload, X } from '@lucide/vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import CaseSquareInlineDiagramPreview from './CaseSquareInlineDiagramPreview.vue'
import CaseSquareHistoryDiagramPicker from './CaseSquareHistoryDiagramPicker.vue'
import CaseSquareFilterDropdown from './CaseSquareFilterDropdown.vue'
import {
  buildGallerySpecPayload,
  DIAGRAM_GALLERY_MAX_ITEMS,
  parseSpecGallery,
  type CaseSquareGalleryImageItem,
  type CaseSquareGalleryItem,
} from './caseSquareGallery'
import {
  CASE_TYPE_PUBLISH_OPTIONS,
  CASE_TEACHING_DOC_MAX_BYTES,
  caseSquareMaxMegabytes,
  dataUrlToPngBlob,
  imageFileToPngBlob,
  isDiagramImageFile,
  isTeachingDocFile,
  isTemplateSourceFile,
  isValidThumbnailBlob,
  DIAGRAM_TYPE_OPTIONS,
  TAG_MAX_LENGTH,
  TAG_MAX_COUNT,
  CASE_ATTACHMENT_MAX_BYTES,
  CASE_VIDEO_MAX_BYTES,
  CASE_UPLOAD_TOTAL_MAX_BYTES,
  type CaseSquareCaseType,
} from './caseSquareShared'
import { useLanguage, useNotifications } from '@/composables'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useCaseSquareMeta } from '@/composables/caseSquare/useCaseSquareMeta'
import { eventBus } from '@/composables/core/useEventBus'
import { setPresentationDiagramEditLocked } from '@/composables/presentation/presentationDiagramEdit'
import { useDiagramStore } from '@/stores'
import { useSavedDiagramsStore, type SavedDiagram } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { createCaseSquarePost, getCaseSquarePost, proxyCreateCaseSquarePost, updateCaseSquarePost, uploadCaseSquareGalleryImages, type CaseSquarePost } from '@/utils/apiClient'
import {
  cloneCaseSquareDiagramSpec,
  decodeMgUploadSpec,
  fetchDiagramSpecPngBlob,
  inferDiagramTypeFromSpec,
  resolveCaseSquareDiagramType,
} from '@/utils/caseSquareDiagramThumbnail'
import {
  captureTeachingDocThumbnail,
} from '@/utils/captureTeachingDocThumbnail'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

function isSessionExpiredMessage(message: string): boolean {
  return (
    message === 'SESSION_EXPIRED' ||
    /session expired|invalidated|login again|会话已过期|请重新登录/i.test(message)
  )
}

const props = defineProps<{
  visible: boolean
  proxyMode?: boolean
  editPostId?: string | null
  diagramType?: string
  getDiagramSpec?: () => Record<string, unknown> | null
  getTitle?: () => string
  prepareForThumbnail?: () => Promise<void>
  getContainer?: () => HTMLElement | null
  restoreAfterThumbnail?: () => void
  defaultCaseType?: CaseSquareCaseType
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { can } = useAdminAccess()
const { subjectOptions, gradeOptions, recommendedTags: metaRecommendedTags } = useCaseSquareMeta()
const savedDiagramsStore = useSavedDiagramsStore()
const diagramStore = useDiagramStore()

const uploadedMgSpec = ref<Record<string, unknown> | null>(null)
const isMgSpecDecoding = ref(false)
const isStep1Advancing = ref(false)
const showThumbnailCapture = ref(false)
const thumbnailCaptureHost = ref<HTMLElement | null>(null)
const inlinePreviewRef = ref<InstanceType<typeof CaseSquareInlineDiagramPreview> | null>(null)

const TITLE_MAX_LENGTH = 40

const step = ref(1)
const title = ref('')
const description = ref('')
const designHighlights = ref('')
const tags = ref<string[]>([])
const tagDraft = ref('')
const caseType = ref<CaseSquareCaseType>('teaching_design')
const subject = ref('')
const grade = ref('')
const diagramType = ref('')
const teachingReflection = ref('')
const classroomApplication = ref('')
const isSubmitting = ref(false)
const isGenerating = ref(false)
const isHistorySpecLoading = ref(false)
const showHistoryPicker = ref(false)

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

type GalleryImageDraft = { id: string; file: File; filename: string; previewUrl: string }
type GalleryDiagramDraft = {
  id: string
  diagram: SavedDiagram
  spec: Record<string, unknown> | null
  title: string
}
type GalleryExistingImage = { path: string; filename: string; url: string }

const galleryImageDrafts = ref<GalleryImageDraft[]>([])
const galleryDiagramDrafts = ref<GalleryDiagramDraft[]>([])
const galleryExistingImages = ref<GalleryExistingImage[]>([])

const galleryTotalCount = computed(
  () =>
    galleryImageDrafts.value.length +
    galleryDiagramDrafts.value.length +
    galleryExistingImages.value.length
)

const galleryAtLimit = computed(() => galleryTotalCount.value >= DIAGRAM_GALLERY_MAX_ITEMS)

function clearGalleryDrafts(): void {
  for (const draft of galleryImageDrafts.value) {
    URL.revokeObjectURL(draft.previewUrl)
  }
  galleryImageDrafts.value = []
  galleryDiagramDrafts.value = []
  galleryExistingImages.value = []
}

function newGalleryId(): string {
  return `g-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

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
      notify.error(String(t('caseSquare.publishModal.invalidMgFile')))
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
const canAutoApprove = computed(() => props.proxyMode && can('tab.case_square.edit'))
const modalTitle = computed(() => {
  if (isEditMode.value) return String(t('caseSquare.publishModal.editTitle'))
  if (props.proxyMode) return String(t('admin.caseSquare.proxyFormTitle'))
  return String(t('caseSquare.publishModal.title'))
})
const submitButtonLabel = computed(() =>
  isEditMode.value
    ? String(t('caseSquare.publishModal.resubmit'))
    : String(t('caseSquare.publishModal.submit'))
)
const isDiagramType = computed(
  () => caseType.value === 'diagram_case' || caseType.value === 'diagram_template'
)

const isDiagramTemplate = computed(() => caseType.value === 'diagram_template')
const isDiagramCase = computed(() => caseType.value === 'diagram_case')

const publishDiagramPreviewSpec = computed(() => {
  if (isDiagramTemplate.value) {
    return uploadedMgSpec.value ?? selectedDiagramSpec.value
  }
  if (isDiagramCase.value) {
    const firstDiagram = galleryDiagramDrafts.value.find((entry) => entry.spec)
    return firstDiagram?.spec ?? selectedDiagramSpec.value
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
  if (caseType.value === 'teaching_design') return Boolean(uploadedFile.value)
  if (caseType.value === 'diagram_template') {
    return hasTemplateStep1Source()
  }
  if (caseType.value === 'diagram_case') {
    return galleryTotalCount.value > 0
  }
  return Boolean(uploadedFile.value || selectedDiagram.value)
})

const currentStepTitle = computed(() =>
  step.value === 1
    ? String(t('caseSquare.publishModal.step1Title'))
    : String(t('caseSquare.publishModal.step2Title'))
)

function resetForm() {
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

async function loadEditPost(postId: string) {
  isEditLoading.value = true
  try {
    const loaded = await getCaseSquarePost(postId)
    if (!loaded.can_resubmit && !loaded.can_edit) {
      notify.error(String(t('caseSquare.detail.loadFailed')))
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
                (entry): entry is CaseSquareGalleryImageItem =>
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
                spec: item.spec ? cloneCaseSquareDiagramSpec(item.spec) : null,
                title: item.title ?? item.diagram_id,
              })
            }
          }
        } else if (spec && typeof spec === 'object') {
          const gallery = parseSpecGallery(spec)
          if (gallery.length > 0) {
            const missingImages = gallery.filter((entry) => entry.kind === 'image' && !entry.path).length
            if (missingImages > 0) {
              notify.warning(String(t('caseSquare.publishModal.galleryReuploadHint')))
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
                  spec: entry.spec ? cloneCaseSquareDiagramSpec(entry.spec) : null,
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
              spec: cloneCaseSquareDiagramSpec(spec),
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
    notify.error(e instanceof Error ? e.message : String(t('caseSquare.detail.loadFailed')))
    emit('update:visible', false)
  } finally {
    isEditLoading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      props.restoreAfterThumbnail?.()
      return
    }
    resetForm()
    title.value = props.getTitle?.() || ''
    caseType.value = props.defaultCaseType || (props.getDiagramSpec ? 'diagram_case' : 'teaching_design')
    diagramType.value = props.diagramType || 'mind_map'
    if (props.editPostId?.trim()) {
      void loadEditPost(props.editPostId.trim())
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
  if (type === 'teaching_design') {
    diagramType.value = ''
    selectedDiagram.value = null
    selectedDiagramSpec.value = null
  } else if (!diagramType.value) {
    diagramType.value = props.diagramType || 'mind_map'
  }
  uploadedFile.value = null
  uploadedFileName.value = ''
  uploadedMgSpec.value = null
})

function addTag() {
  const value = tagDraft.value.trim()
  if (!value) return
  if (tags.value.length >= TAG_MAX_COUNT) {
    notify.warning(String(t('caseSquare.publishModal.tagMaxCount', { max: TAG_MAX_COUNT })))
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
  emit('update:visible', false)
}

function validateFile(file: File): boolean {
  if (caseType.value === 'teaching_design') return isTeachingDocFile(file.name)
  if (caseType.value === 'diagram_case') return isDiagramImageFile(file.name)
  return isTemplateSourceFile(file.name)
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
      t('caseSquare.publishModal.teachingDocTooLarge', {
        maxMb: caseSquareMaxMegabytes(CASE_TEACHING_DOC_MAX_BYTES),
      })
    )
  )
  return false
}

function onDiagramGalleryImagesInput(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = input.files ? Array.from(input.files) : []
  input.value = ''
  if (!files.length) return

  for (const file of files) {
    if (galleryAtLimit.value) {
      notify.error(String(t('caseSquare.publishModal.galleryLimit', { max: DIAGRAM_GALLERY_MAX_ITEMS })))
      break
    }
    if (!validateFile(file)) {
      notify.error(String(t('caseSquare.publishModal.invalidFileType')))
      continue
    }
    if (!validateTeachingDocSize(file)) continue
    galleryImageDrafts.value.push({
      id: newGalleryId(),
      file,
      filename: file.name,
      previewUrl: URL.createObjectURL(file),
    })
  }
}

function removeGalleryImageDraft(id: string): void {
  const index = galleryImageDrafts.value.findIndex((entry) => entry.id === id)
  if (index < 0) return
  URL.revokeObjectURL(galleryImageDrafts.value[index].previewUrl)
  galleryImageDrafts.value.splice(index, 1)
}

function removeGalleryExistingImage(index: number): void {
  galleryExistingImages.value.splice(index, 1)
}

function removeGalleryDiagramDraft(id: string): void {
  galleryDiagramDrafts.value = galleryDiagramDrafts.value.filter((entry) => entry.id !== id)
}

async function loadGalleryDiagramSpec(draft: GalleryDiagramDraft): Promise<boolean> {
  if (draft.spec) return true
  try {
    const cached = savedDiagramsStore.getCachedDiagramSpec(draft.diagram.id)
    if (cached) {
      draft.spec = cloneCaseSquareDiagramSpec(cached)
      return true
    }
    const result = await savedDiagramsStore.getDiagram(draft.diagram.id)
    if (result.ok) {
      draft.spec = cloneCaseSquareDiagramSpec(result.diagram.spec)
      return true
    }
  } catch {
    return false
  }
  return false
}

async function addGalleryDiagram(diagram: SavedDiagram): Promise<void> {
  if (galleryDiagramDrafts.value.some((entry) => entry.diagram.id === diagram.id)) {
    notify.error(String(t('caseSquare.publishModal.galleryDuplicateDiagram')))
    return
  }
  if (galleryAtLimit.value) {
    notify.error(String(t('caseSquare.publishModal.galleryLimit', { max: DIAGRAM_GALLERY_MAX_ITEMS })))
    return
  }
  const draft: GalleryDiagramDraft = {
    id: newGalleryId(),
    diagram,
    spec: null,
    title: diagram.title,
  }
  const cachedSpec = savedDiagramsStore.getCachedDiagramSpec(diagram.id)
  if (cachedSpec) {
    draft.spec = cloneCaseSquareDiagramSpec(cachedSpec)
  }
  galleryDiagramDrafts.value.push(draft)
  if (!diagramType.value) {
    diagramType.value = diagramTypeFromSavedDiagram(diagram.diagram_type) || 'mind_map'
  }
  if (!draft.spec) {
    await loadGalleryDiagramSpec(draft)
  }
}

function onFileInput(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!validateFile(file)) {
    notify.error(String(t('caseSquare.publishModal.invalidFileType')))
    return
  }
  if (!validateTeachingDocSize(file)) return
  uploadedFile.value = file
  uploadedFileName.value = file.name
  selectedDiagram.value = null
  selectedDiagramSpec.value = null
  uploadedMgSpec.value = null

  if (isMgUploadedFile(file)) {
    void ensureMgUploadSpecReady()
  }
}

function removeUploadedFile() {
  uploadedFile.value = null
  uploadedFileName.value = ''
  uploadedMgSpec.value = null
  selectedDiagram.value = null
  selectedDiagramSpec.value = null
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
    selectedDiagramSpec.value = cloneCaseSquareDiagramSpec(spec)
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
    notify.error(String(t('caseSquare.publishModal.validationFile')))
    return false
  } catch {
    notify.error(String(t('caseSquare.publishModal.networkError')))
    return false
  } finally {
    isHistorySpecLoading.value = false
  }
}

async function onHistorySelect(diagram: SavedDiagram) {
  if (isDiagramCase.value) {
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
        notify.error(String(t('caseSquare.publishModal.validationFile')))
      }
    } else {
      notify.error(String(t('caseSquare.publishModal.validationFile')))
    }
  } catch {
    notify.error(String(t('caseSquare.publishModal.networkError')))
  } finally {
    isHistorySpecLoading.value = false
  }
}

async function goNext() {
  if (props.proxyMode && !attributionName.value.trim()) {
    notify.error(String(t('admin.caseSquare.proxyAttributionRequired')))
    return
  }
  if (!title.value.trim()) {
    notify.error(String(t('caseSquare.publishModal.validationTitle')))
    return
  }
  if (!subject.value) {
    notify.error(String(t('caseSquare.publishModal.validationSubject')))
    return
  }
  if (!grade.value) {
    notify.error(String(t('caseSquare.publishModal.validationGrade')))
    return
  }
  if (isDiagramType.value && !diagramType.value) {
    notify.error(String(t('caseSquare.publishModal.validationDiagramType')))
    return
  }
  if (!fromCanvas.value && caseType.value === 'teaching_design' && !uploadedFile.value) {
    notify.error(String(t('caseSquare.publishModal.validationFile')))
    return
  }
  isStep1Advancing.value = true
  try {
    if (!fromCanvas.value && caseType.value === 'diagram_template') {
      if (!hasTemplateStep1Source()) {
        notify.error(String(t('caseSquare.publishModal.validationFile')))
        return
      }
      if (isMgUploadedFile(uploadedFile.value) && !uploadedMgSpec.value) {
        const mgReady = await ensureMgUploadSpecReady()
        if (!mgReady) return
      }
    }
    if (
      !fromCanvas.value &&
      caseType.value === 'diagram_case' &&
      galleryTotalCount.value < 1
    ) {
      notify.error(String(t('caseSquare.publishModal.validationFile')))
      return
    }
    if (
      !fromCanvas.value &&
      caseType.value === 'diagram_case' &&
      galleryDiagramDrafts.value.some((draft) => !draft.spec)
    ) {
      for (const draft of galleryDiagramDrafts.value) {
        if (!draft.spec && !(await loadGalleryDiagramSpec(draft))) {
          notify.error(String(t('caseSquare.publishModal.validationFile')))
          return
        }
      }
    }
    if (!fromCanvas.value && caseType.value === 'diagram_template' && selectedDiagram.value && !selectedDiagramSpec.value) {
      const specReady = await ensureSelectedDiagramSpec()
      if (!specReady) return
    }
    step.value = 2
  } finally {
    isStep1Advancing.value = false
  }
}

function goPrev() {
  step.value = 1
}

async function generateDescription() {
  if (!title.value.trim()) {
    notify.error(String(t('caseSquare.publishModal.validationTitle')))
    return
  }
  isGenerating.value = true
  try {
    await new Promise((r) => setTimeout(r, 600))
    const typeLabel =
      caseType.value === 'teaching_design'
        ? String(t('caseSquare.type.teachingDesign'))
        : caseType.value === 'diagram_case'
          ? String(t('caseSquare.type.diagramCase'))
          : String(t('caseSquare.type.diagramTemplate'))
    const subjectPart = subject.value ? `适用于${subject.value}学科` : ''
    description.value = `《${title.value.trim()}》是一则${typeLabel}案例，${subjectPart}，展示了思维图示在课堂教学中的创新应用与实践价值。`
  } finally {
    isGenerating.value = false
  }
}

async function captureCanvasThumbnail(): Promise<Blob | null> {
  const container = props.getContainer?.()
  if (!container) return null
  await props.prepareForThumbnail?.()
  const htmlToImage = await import('html-to-image')
  const dataUrl = await htmlToImage.toPng(container, { pixelRatio: 2, cacheBust: true })
  return dataUrlToPngBlob(dataUrl)
}

async function captureSpecThumbnailClient(
  spec: Record<string, unknown>,
  diagramTypeValue: string
): Promise<Blob | null> {
  const specClone = cloneCaseSquareDiagramSpec(spec)
  const normalizedType = resolveCaseSquareDiagramType(specClone, diagramTypeValue)
  const backup = {
    type: diagramStore.type,
    spec: diagramStore.getSpecForSave() as Record<string, unknown> | null,
  }

  if (!diagramStore.loadFromSpec(specClone, normalizedType, { emitLoaded: false })) {
    return null
  }

  showThumbnailCapture.value = true
  setPresentationDiagramEditLocked(true)
  try {
    await nextTick()
    await waitForNextPaint()
    eventBus.emit('view:fit_to_canvas_requested', { animate: false, forExport: true })
    try {
      await new Promise<void>((resolve, reject) => {
        let off: (() => void) | null = null
        const timer = window.setTimeout(() => {
          off?.()
          reject(new Error('fit timeout'))
        }, 12_000)
        off = eventBus.once('view:fit_completed', () => {
          window.clearTimeout(timer)
          resolve()
        })
      })
    } catch {
      // Best-effort fit before capture.
    }
    await waitForNextPaint()
    await new Promise((resolve) => setTimeout(resolve, 600))
    const container = thumbnailCaptureHost.value
    if (!container) return null
    const captureTarget =
      (container.querySelector('.diagram-canvas') as HTMLElement | null) ?? container
    const htmlToImage = await import('html-to-image')
    const dataUrl = await htmlToImage.toPng(captureTarget, { pixelRatio: 2, cacheBust: true })
    const blob = await dataUrlToPngBlob(dataUrl)
    return isValidThumbnailBlob(blob) ? blob : null
  } catch {
    return null
  } finally {
    showThumbnailCapture.value = false
    setPresentationDiagramEditLocked(false)
    if (backup.type && backup.spec) {
      diagramStore.loadFromSpec(backup.spec, backup.type as DiagramType, { emitLoaded: false })
    }
  }
}

async function resolveHistoryDiagramThumbnail(): Promise<Blob | null> {
  const diagram = selectedDiagram.value
  if (!diagram) return null

  if (diagram.thumbnail) {
    const fromList = await dataUrlToPngBlob(diagram.thumbnail)
    if (isValidThumbnailBlob(fromList)) return fromList
  }

  const cached = savedDiagramsStore.getCachedDiagram(diagram.id)
  if (cached?.thumbnail) {
    const fromCache = await dataUrlToPngBlob(cached.thumbnail)
    if (isValidThumbnailBlob(fromCache)) return fromCache
  }

  try {
    const res = await fetch(`/api/diagrams/${diagram.id}/png`, {
      credentials: 'include',
    })
    if (res.ok) {
      const data = (await res.json()) as { url?: string }
      if (data.url) {
        const imgRes = await fetch(data.url, { credentials: 'include', cache: 'no-store' })
        if (imgRes.ok) {
          const blob = await imgRes.blob()
          if (isValidThumbnailBlob(blob)) return blob
        }
      }
    }
  } catch {
    // fall through
  }

  return null
}

async function resolveSpecThumbnail(
  spec: Record<string, unknown>,
  diagramTypeValue: string
): Promise<Blob | null> {
  const fromClient = await captureSpecThumbnailClient(spec, diagramTypeValue)
  if (fromClient) return fromClient
  return fetchDiagramSpecPngBlob(spec, diagramTypeValue)
}

async function resolveThumbnail(): Promise<Blob | null> {
  if (fromCanvas.value) {
    return captureCanvasThumbnail()
  }
  const firstGalleryImage = galleryImageDrafts.value[0]
  if (firstGalleryImage) {
    return imageFileToPngBlob(firstGalleryImage.file)
  }
  if (uploadedFile.value && isDiagramImageFile(uploadedFile.value.name)) {
    return imageFileToPngBlob(uploadedFile.value)
  }

  if (showPublishDiagramPreview.value && inlinePreviewRef.value) {
    const fromInline = await inlinePreviewRef.value.captureThumbnail()
    if (isValidThumbnailBlob(fromInline)) return fromInline
  }

  if (uploadedMgSpec.value) {
    const fromSpec = await resolveSpecThumbnail(uploadedMgSpec.value, publishPreviewDiagramType.value)
    if (fromSpec) return fromSpec
  }

  if (selectedDiagramSpec.value) {
    const fromSpec = await resolveSpecThumbnail(
      selectedDiagramSpec.value,
      publishPreviewDiagramType.value
    )
    if (fromSpec) return fromSpec
  }

  if (selectedDiagram.value) {
    const fromHistory = await resolveHistoryDiagramThumbnail()
    if (fromHistory) return fromHistory
  }

  return null
}

function countResolvedGalleryImages(post: { gallery_items?: Array<{ kind: string; url?: string | null; missing?: boolean }> }): number {
  return (
    post.gallery_items?.filter(
      (item) => item.kind === 'image' && item.url && !item.missing
    ).length ?? 0
  )
}

async function buildGalleryRetryFormData(
  post: CaseSquarePost,
  drafts: Array<{ file: File; filename: string }>
): Promise<FormData> {
  const formData = new FormData()
  formData.append('title', post.title)
  formData.append('description', post.description ?? '')
  formData.append('tags', JSON.stringify(post.tags ?? []))
  formData.append('case_type', post.case_type)
  formData.append('subject', post.subject ?? '')
  formData.append('grade', post.grade ?? '')
  if (post.diagram_type) {
    formData.append('diagram_type', post.diagram_type)
  }

  let specObj: Record<string, unknown> = { type: post.case_type, source: 'gallery' }
  if (post.spec_json_url) {
    const specRes = await fetch(post.spec_json_url, { credentials: 'include' })
    if (specRes.ok) {
      const parsed: unknown = await specRes.json()
      if (parsed && typeof parsed === 'object') {
        specObj = parsed as Record<string, unknown>
      }
    }
  }
  formData.append('spec', JSON.stringify(specObj))
  for (const draft of drafts) {
    formData.append('gallery_images', draft.file, draft.filename)
  }
  return formData
}

async function ensureGalleryImagesPersisted(
  postId: string,
  drafts: Array<{ file: File; filename: string }>
): Promise<void> {
  if (drafts.length === 0) return

  let post = await getCaseSquarePost(postId)
  if (countResolvedGalleryImages(post) >= drafts.length) return

  const uploadFormData = new FormData()
  for (const draft of drafts) {
    uploadFormData.append('gallery_images', draft.file, draft.filename)
  }
  let dedicatedEndpointFailed = false
  try {
    const uploaded = await uploadCaseSquareGalleryImages(postId, uploadFormData)
    post = uploaded.post
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    const endpointUnavailable =
      message.includes('405') ||
      message.includes('404') ||
      message.toLowerCase().includes('not found') ||
      message.toLowerCase().includes('method not allowed')
    if (!endpointUnavailable) {
      throw error
    }
    dedicatedEndpointFailed = true
    post = await getCaseSquarePost(postId)
  }

  if (countResolvedGalleryImages(post) < drafts.length) {
    const retryForm = await buildGalleryRetryFormData(post, drafts)
    const updated = await updateCaseSquarePost(postId, retryForm)
    post = updated.post
  }

  if (countResolvedGalleryImages(post) < drafts.length) {
    const hint = dedicatedEndpointFailed
      ? String(t('caseSquare.publishModal.galleryReuploadHint'))
      : ''
    throw new Error(
      hint
        ? `${String(t('caseSquare.publishModal.galleryUploadFailed'))} ${hint}`
        : String(t('caseSquare.publishModal.galleryUploadFailed'))
    )
  }
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
      return String(t('caseSquare.publishModal.fileTooLarge', { name: file.name, maxMb }))
    }
    total += file.size
  }
  if (total > CASE_UPLOAD_TOTAL_MAX_BYTES) {
    return String(t('caseSquare.publishModal.uploadTotalTooLarge'))
  }
  return null
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
    let galleryUploadDrafts: Array<{ file: File; filename: string }> = []
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
      if (autoApprove.value && can('tab.case_square.edit')) {
        formData.append('auto_approve', 'true')
      }
    }

    if (caseType.value === 'teaching_design') {
      if (!uploadedFile.value && !(isEditMode.value && editHasAttachment.value)) {
        notify.error(String(t('caseSquare.publishModal.validationFile')))
        return
      }
      if (uploadedFile.value) {
        formData.append('attachment', uploadedFile.value, uploadedFile.value.name)
      }
      const teachingThumb = uploadedFile.value
        ? await captureTeachingDocThumbnail(uploadedFile.value)
        : null
      if (teachingThumb) {
        formData.append('thumbnail', teachingThumb, 'thumbnail.png')
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
          notify.error(String(t('caseSquare.publishModal.validationFile')))
          return
        }
        for (const draft of galleryDiagramDrafts.value) {
          if (!(await loadGalleryDiagramSpec(draft))) {
            notify.error(String(t('caseSquare.publishModal.validationFile')))
            return
          }
        }
        const galleryItems: CaseSquareGalleryItem[] = []
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
            spec: cloneCaseSquareDiagramSpec(draft.spec!),
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
        galleryUploadDrafts = galleryImageDrafts.value.map((draft) => ({
          file: draft.file,
          filename: draft.filename,
        }))
        for (const draft of galleryUploadDrafts) {
          formData.append('gallery_images', draft.file, draft.filename)
        }
        const thumb = await resolveThumbnail()
        if (thumb) {
          formData.append('thumbnail', thumb, 'thumbnail.png')
        }
      } else {
        let specObj: Record<string, unknown> | null = null

        if (fromCanvas.value) {
          specObj = props.getDiagramSpec?.() ?? null
        } else if (selectedDiagramSpec.value) {
          specObj = cloneCaseSquareDiagramSpec(selectedDiagramSpec.value)
        } else if (uploadedMgSpec.value) {
          specObj = cloneCaseSquareDiagramSpec(uploadedMgSpec.value)
          if (uploadedFile.value) {
            formData.append('source_file', uploadedFile.value, uploadedFile.value.name)
          }
        } else if (caseType.value === 'diagram_template') {
          notify.error(String(t('caseSquare.publishModal.validationFile')))
          return
        } else if (uploadedFile.value?.name.toLowerCase().endsWith('.mg')) {
          notify.error(String(t('caseSquare.publishModal.invalidMgFile')))
          return
        } else {
          specObj = { type: caseType.value, source: 'image_upload' }
        }

        if (!specObj) {
          if (isEditMode.value && selectedDiagramSpec.value) {
            specObj = cloneCaseSquareDiagramSpec(selectedDiagramSpec.value)
          } else {
            notify.error(String(t('community.shareModal.noDiagramData')))
            return
          }
        }

        Object.assign(specObj, buildSpecExtras())
        formData.append('spec', JSON.stringify(specObj))

        if (uploadedFile.value && !uploadedFile.value.name.toLowerCase().endsWith('.mg')) {
          formData.append('source_file', uploadedFile.value, uploadedFile.value.name)
        }

        const thumb = await resolveThumbnail()
        if (thumb) {
          formData.append('thumbnail', thumb, 'thumbnail.png')
        }
      }
    }

    if (props.proxyMode) {
      await proxyCreateCaseSquarePost(formData)
      notify.success(String(t('admin.caseSquare.proxySuccess')), 3000)
    } else {
      let savedPostId = props.editPostId?.trim() ?? ''
      if (isEditMode.value && savedPostId) {
        await updateCaseSquarePost(savedPostId, formData)
        notify.success(String(t('caseSquare.resubmitted')), 3000)
      } else {
        const result = await createCaseSquarePost(formData)
        savedPostId = result.post.id
        notify.success(String(t('caseSquare.publishModal.success')), 3000)
      }

      if (galleryUploadDrafts.length > 0 && savedPostId) {
        await ensureGalleryImagesPersisted(savedPostId, galleryUploadDrafts)
      }
    }
    emit('update:visible', false)
    emit('success')
    resetForm()
  } catch (e) {
    const message = e instanceof Error ? e.message : ''
    if (isSessionExpiredMessage(message)) {
      notify.error(String(t('auth.sessionExpired')))
    } else if (message === 'NETWORK_ERROR' || message === 'Failed to fetch') {
      notify.error(String(t('caseSquare.publishModal.networkError')))
    } else {
      notify.error(message || 'Failed')
    }
  } finally {
    isSubmitting.value = false
  }
}

const uploadAccept = computed(() => {
  if (caseType.value === 'teaching_design') return '.doc,.docx,.pdf'
  if (caseType.value === 'diagram_case') return '.png,.jpg,.jpeg,.webp,.gif'
  return '.mg'
})

function caseTypeIcon(type: CaseSquareCaseType) {
  if (type === 'teaching_design') return BookOpen
  if (type === 'diagram_case') return ImageIcon
  return LayoutTemplate
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="close"
    >
      <div
        :class="[
          'flex h-[min(92vh,880px)] w-full overflow-hidden rounded-2xl bg-white shadow-2xl',
          showPublishDiagramPreview && step === 1 ? 'max-w-6xl' : 'max-w-4xl',
        ]"
      >
        <!-- Left step nav -->
        <aside class="flex w-44 shrink-0 flex-col border-r border-gray-100 bg-gray-50 p-5">
          <h2 class="mb-6 text-sm font-bold text-gray-900">
            {{ modalTitle }}
          </h2>

          <div class="flex gap-3">
            <div class="flex flex-col items-center">
              <div
                :class="[
                  'publish-step-dot',
                  step >= 1 ? 'publish-step-dot--active' : '',
                ]"
              >
                1
              </div>
              <div
                :class="[
                  'publish-step-line',
                  step >= 2 ? 'publish-step-line--active' : '',
                ]"
              />
              <div
                :class="[
                  'publish-step-dot',
                  step >= 2 ? 'publish-step-dot--active' : '',
                ]"
              >
                2
              </div>
            </div>
            <div class="flex flex-1 flex-col gap-8 pt-0.5">
              <div>
                <p :class="['text-sm font-medium', step >= 1 ? 'text-gray-900' : 'text-gray-400']">
                  {{ t('caseSquare.publishModal.step1Title') }}
                </p>
                <p class="text-xs text-gray-400">{{ t('caseSquare.publishModal.step1Desc') }}</p>
              </div>
              <div>
                <p :class="['text-sm font-medium', step >= 2 ? 'text-gray-900' : 'text-gray-400']">
                  {{ t('caseSquare.publishModal.step2Title') }}
                </p>
                <p class="text-xs text-gray-400">{{ t('caseSquare.publishModal.step2Desc') }}</p>
              </div>
            </div>
          </div>
        </aside>

        <div class="flex min-w-0 flex-1">
          <div
            v-if="showPublishDiagramPreview"
            :class="[
              'flex min-w-0 flex-col border-r border-gray-100 bg-gray-50',
              step === 1
                ? 'relative w-[42%]'
                : 'pointer-events-none fixed -left-[12000px] top-0 z-[-1] h-[720px] w-[960px]',
            ]"
          >
            <div
              v-if="step === 1"
              class="shrink-0 border-b border-gray-100 bg-white px-4 py-3"
            >
              <p class="text-sm font-medium text-gray-700">
                {{
                  t(
                    isDiagramTemplate
                      ? 'caseSquare.publishModal.templatePreviewLabel'
                      : 'caseSquare.publishModal.diagramCasePreviewLabel'
                  )
                }}
              </p>
              <p class="mt-0.5 text-xs text-gray-400">
                {{
                  t(
                    isDiagramTemplate
                      ? 'caseSquare.publishModal.templatePreviewHint'
                      : 'caseSquare.publishModal.diagramCasePreviewHint'
                  )
                }}
              </p>
            </div>
            <div class="min-h-0 flex-1 min-h-[360px]">
              <CaseSquareInlineDiagramPreview
                ref="inlinePreviewRef"
                :spec="publishDiagramPreviewSpec"
                :diagram-type="publishPreviewDiagramType"
                :thumbnail-url="publishDiagramPreviewThumbnail"
              />
            </div>
          </div>

          <!-- Right content -->
          <div class="flex min-w-0 flex-1 flex-col">
          <div class="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <h3 class="text-base font-semibold text-gray-900">{{ currentStepTitle }}</h3>
            <button
              type="button"
              class="publish-modal-close rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              @click="close"
            >
              <X class="h-5 w-5" />
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-6 py-5">
            <!-- Step 1 -->
            <template v-if="step === 1">
              <div
                v-if="proxyMode"
                class="mb-5 rounded-xl border border-amber-100 bg-amber-50/60 p-4"
              >
                <p class="mb-3 text-sm font-medium text-gray-900">
                  {{ t('admin.caseSquare.proxyAttributionTitle') }}
                </p>
                <div class="mb-3">
                  <label class="mb-1 block text-sm text-gray-700">
                    {{ t('admin.caseSquare.proxyAuthorName') }}
                    <span class="text-red-500">*</span>
                  </label>
                  <input
                    v-model="attributionName"
                    type="text"
                    maxlength="100"
                    class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                  />
                </div>
                <div>
                  <label class="mb-1 block text-sm text-gray-700">
                    {{ t('admin.caseSquare.proxyAuthorOrg') }}
                  </label>
                  <input
                    v-model="attributionOrg"
                    type="text"
                    maxlength="200"
                    class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                  />
                </div>
              </div>

              <div v-if="fromCanvas" class="mb-4 rounded-xl bg-gray-50 px-4 py-2 text-sm text-gray-600">
                {{ t('caseSquare.publishModal.fromCanvas') }}
              </div>

              <div v-if="!fromCanvas" class="mb-5">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('caseSquare.publishModal.caseTypeLabel') }}
                  <span class="text-red-500">*</span>
                </label>
                <div class="grid grid-cols-3 gap-3">
                  <button
                    v-for="opt in CASE_TYPE_PUBLISH_OPTIONS"
                    :key="opt.value"
                    type="button"
                    :disabled="isEditMode"
                    :class="[
                      'flex flex-col items-center rounded-2xl px-3 py-5 text-center transition-all',
                      caseType === opt.value
                        ? 'border-2 border-gray-900 bg-gray-50'
                        : 'border border-gray-200 bg-white hover:border-gray-300',
                      isEditMode ? 'cursor-default opacity-70' : '',
                    ]"
                    @click="!isEditMode && (caseType = opt.value)"
                  >
                    <component
                      :is="caseTypeIcon(opt.value)"
                      :class="[
                        'mb-2.5 h-6 w-6',
                        caseType === opt.value ? 'text-gray-900' : 'text-gray-400',
                      ]"
                    />
                    <span class="text-sm font-semibold text-gray-900">{{ t(opt.labelKey) }}</span>
                    <span class="mt-1.5 text-[11px] leading-snug text-gray-400">
                      {{ t(opt.descKey) }}
                    </span>
                  </button>
                </div>
              </div>

              <div class="mb-4">
                <div class="mb-2 flex items-end justify-between">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">
                      {{ t('caseSquare.publishModal.titleLabel') }}
                      <span class="text-red-500">*</span>
                    </label>
                    <p class="mt-0.5 text-xs text-gray-400">
                      {{ t('caseSquare.publishModal.titleHint', { max: TITLE_MAX_LENGTH }) }}
                    </p>
                  </div>
                  <span
                    :class="[
                      'text-xs tabular-nums',
                      title.length > TITLE_MAX_LENGTH ? 'text-amber-500' : 'text-gray-400',
                    ]"
                  >
                    {{ title.length }}/{{ TITLE_MAX_LENGTH }}
                  </span>
                </div>
                <input
                  v-model="title"
                  type="text"
                  :maxlength="TITLE_MAX_LENGTH"
                  :placeholder="t('caseSquare.publishModal.titlePlaceholder')"
                  class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                />
              </div>

              <div class="mb-4 grid grid-cols-2 gap-5">
                <div class="min-w-0">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('caseSquare.publishModal.subjectLabel') }}
                    <span class="text-red-500">*</span>
                  </label>
                  <CaseSquareFilterDropdown
                    v-model="subject"
                    block
                    variant="plain"
                    :options="subjectFilterOptions"
                    :all-label="t('caseSquare.publishModal.selectSubject')"
                    :include-all="false"
                  />
                </div>
                <div class="min-w-0">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('caseSquare.publishModal.gradeLabel') }}
                    <span class="text-red-500">*</span>
                  </label>
                  <CaseSquareFilterDropdown
                    v-model="grade"
                    block
                    variant="plain"
                    :options="gradeFilterOptions"
                    :all-label="t('caseSquare.publishModal.selectGrade')"
                    :include-all="false"
                  />
                </div>
              </div>

              <div v-if="isDiagramType" class="mb-4">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('caseSquare.publishModal.diagramTypeLabel') }}
                  <span class="text-red-500">*</span>
                </label>
                <div :class="{ 'pointer-events-none opacity-60': diagramTypeFromHistory }">
                  <CaseSquareFilterDropdown
                    v-model="diagramType"
                    block
                    variant="plain"
                    :options="diagramTypeFilterOptions"
                    :all-label="t('caseSquare.publishModal.selectDiagramType')"
                    :include-all="false"
                  />
                </div>
                <p v-if="diagramTypeFromHistory" class="mt-1 text-xs text-gray-400">
                  {{ t('caseSquare.publishModal.diagramTypeAutoMatched') }}
                </p>
              </div>

              <div v-if="!fromCanvas" class="mb-2">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('caseSquare.publishModal.uploadLabel') }}
                  <span class="text-red-500">*</span>
                </label>

                <template v-if="caseType === 'teaching_design'">
                  <label
                    class="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-4 py-8 transition-colors hover:border-gray-300 hover:bg-gray-50"
                  >
                    <Upload class="mb-2 h-8 w-8 text-gray-300" />
                    <span class="text-sm text-gray-500">{{ t('caseSquare.publishModal.uploadFile') }}</span>
                    <span class="mt-1 text-xs text-gray-400">
                      {{
                        t('caseSquare.publishModal.teachingDocHintWithLimit', {
                          maxMb: caseSquareMaxMegabytes(CASE_TEACHING_DOC_MAX_BYTES),
                        })
                      }}
                    </span>
                    <input
                      type="file"
                      class="hidden"
                      :accept="uploadAccept"
                      @change="onFileInput"
                    />
                  </label>
                </template>

                <template v-else-if="caseType === 'diagram_case'">
                  <p class="mb-2 text-xs text-gray-400">
                    {{
                      t('caseSquare.publishModal.galleryHint', {
                        max: DIAGRAM_GALLERY_MAX_ITEMS,
                      })
                    }}
                  </p>
                  <div class="grid grid-cols-2 gap-3">
                    <label
                      class="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors hover:border-gray-300 hover:bg-gray-50"
                      :class="{ 'pointer-events-none opacity-50': galleryAtLimit }"
                    >
                      <Upload class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">
                        {{ t('caseSquare.publishModal.uploadImages') }}
                      </span>
                      <span class="mt-1 text-[10px] text-gray-400">
                        {{ t('caseSquare.publishModal.diagramImageHint') }}
                      </span>
                      <input
                        type="file"
                        class="hidden"
                        multiple
                        :accept="uploadAccept"
                        :disabled="galleryAtLimit"
                        @change="onDiagramGalleryImagesInput"
                      />
                    </label>
                    <button
                      type="button"
                      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors hover:border-gray-300 hover:bg-gray-50"
                      :class="{ 'pointer-events-none opacity-50': galleryAtLimit }"
                      :disabled="galleryAtLimit"
                      @click="showHistoryPicker = true"
                    >
                      <History class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">
                        {{ t('caseSquare.publishModal.pickHistory') }}
                      </span>
                    </button>
                  </div>
                  <div
                    v-if="galleryTotalCount > 0"
                    class="mt-3 space-y-2 rounded-xl border border-gray-100 bg-gray-50 p-3"
                  >
                    <p class="text-xs font-medium text-gray-500">
                      {{ t('caseSquare.publishModal.galleryCount', { count: galleryTotalCount, max: DIAGRAM_GALLERY_MAX_ITEMS }) }}
                    </p>
                    <div class="space-y-2">
                      <div
                        v-for="existing in galleryExistingImages"
                        :key="existing.path"
                        class="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2"
                      >
                        <span class="truncate text-xs text-gray-700">
                          {{ t('caseSquare.publishModal.galleryImageItem', { name: existing.filename }) }}
                        </span>
                        <button
                          type="button"
                          class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                          @click="removeGalleryExistingImage(galleryExistingImages.indexOf(existing))"
                        >
                          {{ t('caseSquare.publishModal.removeFile') }}
                        </button>
                      </div>
                      <div
                        v-for="draft in galleryImageDrafts"
                        :key="draft.id"
                        class="flex items-center gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2"
                      >
                        <img
                          :src="draft.previewUrl"
                          :alt="draft.filename"
                          class="h-10 w-10 shrink-0 rounded object-cover"
                        />
                        <span class="min-w-0 flex-1 truncate text-xs text-gray-700">{{ draft.filename }}</span>
                        <button
                          type="button"
                          class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                          @click="removeGalleryImageDraft(draft.id)"
                        >
                          {{ t('caseSquare.publishModal.removeFile') }}
                        </button>
                      </div>
                      <div
                        v-for="draft in galleryDiagramDrafts"
                        :key="draft.id"
                        class="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2"
                      >
                        <span class="truncate text-xs text-gray-700">
                          {{ t('caseSquare.publishModal.galleryDiagramItem', { name: draft.title }) }}
                        </span>
                        <button
                          type="button"
                          class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                          @click="removeGalleryDiagramDraft(draft.id)"
                        >
                          {{ t('caseSquare.publishModal.removeFile') }}
                        </button>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <div class="grid grid-cols-2 gap-3">
                    <label
                      class="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors hover:border-gray-300 hover:bg-gray-50"
                    >
                      <Upload class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">{{ t('caseSquare.publishModal.uploadFile') }}</span>
                      <span class="mt-1 text-[10px] text-gray-400">
                        {{ t('caseSquare.publishModal.templateFileHint') }}
                      </span>
                      <input
                        type="file"
                        class="hidden"
                        :accept="uploadAccept"
                        @change="onFileInput"
                      />
                    </label>
                    <button
                      type="button"
                      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors hover:border-gray-300 hover:bg-gray-50"
                      @click="showHistoryPicker = true"
                    >
                      <History class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">
                        {{ t('caseSquare.publishModal.pickHistory') }}
                      </span>
                    </button>
                  </div>
                </template>

                <div
                  v-if="uploadedFileName && caseType !== 'diagram_case'"
                  class="mt-3 flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
                >
                  <span class="truncate text-sm text-gray-700">{{ uploadedFileName }}</span>
                  <button
                    type="button"
                    class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                    @click="removeUploadedFile"
                  >
                    {{ t('caseSquare.publishModal.removeFile') }}
                  </button>
                </div>
              </div>
            </template>

            <!-- Step 2 -->
            <template v-else>
              <!-- 简介 -->
              <div class="mb-5">
                <div class="mb-2 flex items-center gap-2">
                  <label class="text-sm font-medium text-gray-700">
                    {{
                      caseType === 'teaching_design'
                        ? t('caseSquare.publishModal.teachingIntroLabel')
                        : t('caseSquare.publishModal.introLabel')
                    }}
                  </label>
                  <button
                    type="button"
                    class="publish-ai-badge"
                    :disabled="isGenerating"
                    @click="generateDescription"
                  >
                    <Sparkles class="h-3 w-3" />
                    {{ t('caseSquare.publishModal.aiGenerate') }}
                  </button>
                </div>
                <textarea
                  v-model="description"
                  rows="4"
                  maxlength="5000"
                  :placeholder="
                    caseType === 'teaching_design'
                      ? t('caseSquare.publishModal.teachingIntroPlaceholder')
                      : t('caseSquare.publishModal.introPlaceholder')
                  "
                  class="publish-field"
                />
              </div>

              <!-- 教学设计：设计亮点 + 教学反思 -->
              <template v-if="caseType === 'teaching_design'">
                <div class="mb-5">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('caseSquare.publishModal.highlightsLabel') }}
                  </label>
                  <textarea
                    v-model="designHighlights"
                    rows="4"
                    maxlength="5000"
                    :placeholder="t('caseSquare.publishModal.highlightsPlaceholder')"
                    class="publish-field"
                  />
                </div>

                <div class="mb-5">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('caseSquare.publishModal.reflectionLabel') }}
                  </label>
                  <textarea
                    v-model="teachingReflection"
                    rows="4"
                    maxlength="5000"
                    :placeholder="t('caseSquare.publishModal.reflectionPlaceholder')"
                    class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                  />
                </div>
              </template>

              <!-- 图示类：课堂应用 -->
              <div v-if="isDiagramType" class="mb-5">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('caseSquare.publishModal.classroomAppLabel') }}
                </label>
                <textarea
                  v-model="classroomApplication"
                  rows="4"
                  maxlength="5000"
                  :placeholder="t('caseSquare.publishModal.classroomAppPlaceholder')"
                  class="publish-field"
                />
              </div>

              <!-- 标签（pill 逐个添加） -->
              <div class="mb-4">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('caseSquare.publishModal.tagsLabel') }}
                  <span class="ml-1 text-xs font-normal text-gray-400">
                    {{ t('caseSquare.publishModal.tagCountHint', { max: TAG_MAX_COUNT }) }}
                  </span>
                </label>
                <div
                  v-if="tags.length > 0"
                  class="mb-2 flex flex-wrap gap-2"
                >
                  <span
                    v-for="(tag, index) in tags"
                    :key="`${tag}-${index}`"
                    class="inline-flex items-center gap-1 rounded-lg bg-gray-100 px-2.5 py-1 text-xs text-gray-700"
                  >
                    {{ tag }}
                    <button
                      type="button"
                      class="publish-tag-remove text-gray-400 hover:text-gray-600"
                      @click="removeTag(index)"
                    >
                      <X class="h-3 w-3" />
                    </button>
                  </span>
                </div>
                <p class="mb-2 text-xs text-gray-400">
                  {{ t('caseSquare.publishModal.tagRecommended') }}
                </p>
                <div class="mb-3 flex flex-wrap gap-2">
                  <button
                    v-for="tag in recommendedTags"
                    :key="tag"
                    type="button"
                    class="publish-tag-suggest"
                    @click="pickRecommendedTag(tag)"
                  >
                    {{ tag }}
                  </button>
                </div>
                <div class="mb-1 flex items-center justify-end">
                  <span
                    :class="[
                      'text-xs tabular-nums',
                      tagDraft.length >= TAG_MAX_LENGTH ? 'text-amber-500' : 'text-gray-400',
                    ]"
                  >
                    {{ tagDraft.length }}/{{ TAG_MAX_LENGTH }}
                  </span>
                </div>
                <div class="flex gap-2">
                  <input
                    v-model="tagDraft"
                    type="text"
                    :maxlength="TAG_MAX_LENGTH"
                    :placeholder="t('caseSquare.publishModal.tagInputPlaceholder')"
                    class="publish-field min-w-0 flex-1"
                    :disabled="tagsAtLimit"
                    @keydown="onTagKeydown"
                  />
                  <button
                    type="button"
                    class="publish-tag-add shrink-0 rounded-xl border border-gray-100 bg-white px-4 py-2.5 text-sm text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="tagsAtLimit"
                    @click="addTag"
                  >
                    {{ t('caseSquare.publishModal.tagAdd') }}
                  </button>
                </div>
              </div>

              <label
                v-if="canAutoApprove && step === 2"
                class="mb-4 flex cursor-pointer items-center gap-2 text-sm text-gray-700"
              >
                <input
                  v-model="autoApprove"
                  type="checkbox"
                />
                {{ t('admin.caseSquare.proxyAutoApprove') }}
              </label>
            </template>
          </div>

          <div class="flex items-center justify-end gap-3 border-t border-gray-100 px-6 py-4">
            <button
              v-if="step === 2"
              type="button"
              class="rounded-xl border border-gray-100 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
              @click="goPrev"
            >
              {{ t('caseSquare.publishModal.prev') }}
            </button>
            <button
              v-if="step === 1"
              type="button"
              class="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!step1Complete || isStep1Advancing || isMgSpecDecoding"
              @click="goNext"
            >
              {{
                isStep1Advancing || isMgSpecDecoding
                  ? t('caseSquare.publishModal.parsingMg')
                  : t('caseSquare.publishModal.next')
              }}
            </button>
            <button
              v-else
              type="button"
              class="rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSubmitting"
              @click="submit"
            >
              {{ submitButtonLabel }}
            </button>
          </div>
        </div>
        </div>
      </div>
    </div>
  </Teleport>

  <CaseSquareHistoryDiagramPicker
    v-model:visible="showHistoryPicker"
    :multi-select="isDiagramCase"
    @select="onHistorySelect"
  />

  <Teleport to="body">
    <div
      v-if="showThumbnailCapture"
      class="pointer-events-none fixed -left-[12000px] top-0 z-0 h-[800px] w-[1200px] overflow-hidden bg-white"
    >
      <div ref="thumbnailCaptureHost" class="h-full w-full">
        <DiagramCanvas :show-minimap="false" :fit-view-on-init="true" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.publish-step-dot {
  display: flex;
  height: 1.75rem;
  width: 1.75rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  background: #e5e7eb;
  color: #6b7280;
}

.publish-step-dot--active {
  background: #111827;
  color: #fff;
}

.publish-step-line {
  width: 2px;
  flex: 1;
  min-height: 3.25rem;
  margin: 2px 0;
  border-radius: 1px;
  background: #e5e7eb;
}

.publish-step-line--active {
  background: #111827;
}

.publish-ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1rem;
  color: #7c3aed;
  background: #f5f3ff;
  border: none;
  border-radius: 0.375rem;
  outline: none;
  box-shadow: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  transition: background-color 0.15s ease;
}

.publish-ai-badge:hover:not(:disabled) {
  background: #ede9fe;
}

.publish-ai-badge:focus,
.publish-ai-badge:focus-visible {
  outline: none;
  box-shadow: none;
}

.publish-ai-badge:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.publish-field {
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid #f3f4f6;
  padding: 0.625rem 1rem;
  font-size: 0.875rem;
  line-height: 1.25rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  outline: none;
}

.publish-field:focus {
  border-color: #e5e7eb;
  box-shadow: 0 0 0 2px rgb(229 231 235 / 0.4);
}

.publish-modal-close {
  border: none;
  outline: none;
  background: transparent;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.publish-modal-close:focus,
.publish-modal-close:focus-visible {
  outline: none;
  box-shadow: none;
}

.publish-tag-suggest {
  padding: 0.25rem 0.625rem;
  font-size: 0.75rem;
  line-height: 1rem;
  color: #4b5563;
  background: #fff;
  border: 1px solid #f3f4f6;
  border-radius: 0.5rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.04);
  outline: none;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}

.publish-tag-suggest:hover {
  border-color: #e5e7eb;
  background: #f9fafb;
}

.publish-tag-suggest:focus,
.publish-tag-suggest:focus-visible {
  outline: none;
  box-shadow: none;
}

.publish-tag-remove,
.publish-tag-add {
  border: none;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  cursor: pointer;
}

.publish-tag-add {
  border: 1px solid #f3f4f6;
}

.publish-tag-remove:focus,
.publish-tag-remove:focus-visible,
.publish-tag-add:focus,
.publish-tag-add:focus-visible {
  outline: none;
}
</style>
