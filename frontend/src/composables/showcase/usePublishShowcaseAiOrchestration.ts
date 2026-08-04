/**
 * Combine teaching-design + diagram Showcase AI copy for the publish modal.
 */
import { computed, type Ref } from 'vue'

import {
  useShowcaseDiagramCopyAi,
  type DiagramCopySpecSource,
} from '@/composables/showcase/useShowcaseDiagramCopyAi'
import { useShowcaseTeachingCopyAi } from '@/composables/showcase/useShowcaseTeachingCopyAi'
import { cloneShowcaseDiagramSpec } from '@/utils/showcaseDiagramThumbnail'

type NotifyLike = {
  info: (message: string) => void
  success: (message: string) => void
  error: (message: string) => void
}

type TranslateFn = (key: string) => unknown

type GalleryDiagramDraft = {
  spec: Record<string, unknown> | null
}

export function usePublishShowcaseAiOrchestration(options: {
  t: TranslateFn
  notify: NotifyLike
  caseType: Ref<string>
  title: Ref<string>
  subject: Ref<string>
  grade: Ref<string>
  uploadedFile: Ref<File | null>
  description: Ref<string>
  designHighlights: Ref<string>
  classroomApplication: Ref<string>
  step: Ref<number>
  isDiagramType: Ref<boolean>
  fromCanvas: Ref<boolean>
  getDiagramSpec?: () => Record<string, unknown> | null
  publishPreviewDiagramType: Ref<string>
  diagramType: Ref<string>
  uploadedMgSpec: Ref<Record<string, unknown> | null>
  selectedDiagramSpec: Ref<Record<string, unknown> | null>
  galleryDiagramDrafts: Ref<GalleryDiagramDraft[]>
}) {
  const {
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
    getDiagramSpec,
    publishPreviewDiagramType,
    diagramType,
    uploadedMgSpec,
    selectedDiagramSpec,
    galleryDiagramDrafts,
  } = options

  function resolveDiagramCopySpecSource(): DiagramCopySpecSource | null {
    const resolvedType =
      publishPreviewDiagramType.value || diagramType.value || 'mind_map'
    if (fromCanvas.value && getDiagramSpec) {
      const canvasSpec = getDiagramSpec()
      if (canvasSpec && typeof canvasSpec === 'object') {
        return {
          specs: [cloneShowcaseDiagramSpec(canvasSpec)],
          diagramType: resolvedType,
        }
      }
    }
    if (caseType.value === 'diagram_case' || caseType.value === 'diagram_template') {
      const specs = galleryDiagramDrafts.value
        .filter((draft) => draft.spec)
        .map((draft) => cloneShowcaseDiagramSpec(draft.spec as Record<string, unknown>))
      if (specs.length > 0) {
        return { specs, diagramType: resolvedType }
      }
      const fallback = uploadedMgSpec.value ?? selectedDiagramSpec.value
      if (fallback) {
        return {
          specs: [cloneShowcaseDiagramSpec(fallback)],
          diagramType: resolvedType,
        }
      }
      return null
    }
    return null
  }

  const {
    isGenerating: teachingIsGenerating,
    aiGeneratePhase: teachingAiGeneratePhase,
    clearTeachingCopyPrefetch,
    beginTeachingCopyPrefetch,
    generateDescription: generateTeachingDescription,
    resetAiCopyFields,
    markDescriptionDirty: markTeachingDescriptionDirty,
    markDesignHighlightsDirty,
  } = useShowcaseTeachingCopyAi({
    t,
    notify,
    caseType,
    title,
    subject,
    grade,
    uploadedFile,
    description,
    designHighlights,
    step,
  })

  const {
    isGenerating: diagramIsGenerating,
    aiGeneratePhase: diagramAiGeneratePhase,
    clearDiagramCopyPrefetch,
    beginDiagramCopyPrefetch,
    generateDiagramCopy,
    markDescriptionDirty: markDiagramDescriptionDirty,
    markClassroomApplicationDirty,
  } = useShowcaseDiagramCopyAi({
    t,
    notify,
    caseType,
    title,
    subject,
    grade,
    description,
    classroomApplication,
    resolveSpecSource: resolveDiagramCopySpecSource,
    step,
  })

  const isGenerating = computed(() =>
    caseType.value === 'teaching_design'
      ? teachingIsGenerating.value
      : diagramIsGenerating.value,
  )

  const aiGeneratePhase = computed(() =>
    caseType.value === 'teaching_design'
      ? teachingAiGeneratePhase.value
      : diagramAiGeneratePhase.value,
  )

  function clearAllAiPrefetch(): void {
    clearTeachingCopyPrefetch()
    clearDiagramCopyPrefetch()
  }

  function generateDescription(): void {
    if (caseType.value === 'teaching_design') {
      generateTeachingDescription()
      return
    }
    if (isDiagramType.value) {
      generateDiagramCopy()
    }
  }

  function markDescriptionDirty(): void {
    if (caseType.value === 'teaching_design') {
      markTeachingDescriptionDirty()
      return
    }
    markDiagramDescriptionDirty()
  }

  function beginStep2AiPrefetch(): void {
    if (caseType.value === 'teaching_design' && uploadedFile.value) {
      beginTeachingCopyPrefetch({
        notifyStart: true,
        notifySuccess: true,
        notifyError: true,
        forceOverwrite: false,
      })
      return
    }
    if (isDiagramType.value && resolveDiagramCopySpecSource()) {
      beginDiagramCopyPrefetch({
        notifyStart: true,
        notifySuccess: true,
        notifyError: true,
        forceOverwrite: false,
      })
    }
  }

  return {
    isGenerating,
    aiGeneratePhase,
    clearAllAiPrefetch,
    clearTeachingCopyPrefetch,
    beginTeachingCopyPrefetch,
    beginDiagramCopyPrefetch,
    beginStep2AiPrefetch,
    generateDescription,
    resetAiCopyFields,
    markDescriptionDirty,
    markDesignHighlightsDirty,
    markClassroomApplicationDirty,
    resolveDiagramCopySpecSource,
  }
}
