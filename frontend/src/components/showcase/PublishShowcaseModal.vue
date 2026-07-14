<script setup lang="ts">
import { Loader2 } from '@lucide/vue'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import ShowcaseInlineDiagramPreview from './ShowcaseInlineDiagramPreview.vue'
import ShowcaseHistoryDiagramPicker from './ShowcaseHistoryDiagramPicker.vue'
import ShowcaseFilterDropdown from './ShowcaseFilterDropdown.vue'
import {
  usePublishShowcaseModal,
  type PublishShowcaseModalProps,
} from '@/composables/showcase/usePublishShowcaseModal'

import './PublishShowcaseModal.css'

const props = defineProps<PublishShowcaseModalProps>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const {
  uploadedMgSpec,
  isMgSpecDecoding,
  isStep1Advancing,
  showThumbnailCapture,
  thumbnailCaptureHost,
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
  isEditMode,
  fromCanvas,
  canAutoApprove,
  modalTitle,
  submitButtonLabel,
  isDiagramType,
  isDiagramTemplate,
  isDiagramCase,
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
  directFileUploadsEnabled,
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
} = usePublishShowcaseModal(props, emit)
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
                  {{ t('showcase.publishModal.step1Title') }}
                </p>
                <p class="text-xs text-gray-400">{{ t('showcase.publishModal.step1Desc') }}</p>
              </div>
              <div>
                <p :class="['text-sm font-medium', step >= 2 ? 'text-gray-900' : 'text-gray-400']">
                  {{ t('showcase.publishModal.step2Title') }}
                </p>
                <p class="text-xs text-gray-400">{{ t('showcase.publishModal.step2Desc') }}</p>
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
                      ? 'showcase.publishModal.templatePreviewLabel'
                      : 'showcase.publishModal.diagramCasePreviewLabel'
                  )
                }}
              </p>
              <p class="mt-0.5 text-xs text-gray-400">
                {{
                  t(
                    isDiagramTemplate
                      ? 'showcase.publishModal.templatePreviewHint'
                      : 'showcase.publishModal.diagramCasePreviewHint'
                  )
                }}
              </p>
            </div>
            <div class="min-h-0 flex-1 min-h-[360px]">
              <ShowcaseInlineDiagramPreview
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
                  {{ t('admin.showcase.proxyAttributionTitle') }}
                </p>
                <div class="mb-3">
                  <label class="mb-1 block text-sm text-gray-700">
                    {{ t('admin.showcase.proxyAuthorName') }}
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
                    {{ t('admin.showcase.proxyAuthorOrg') }}
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
                {{ t('showcase.publishModal.fromCanvas') }}
              </div>

              <div v-if="!fromCanvas" class="mb-5">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('showcase.publishModal.caseTypeLabel') }}
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
                      {{ t('showcase.publishModal.titleLabel') }}
                      <span class="text-red-500">*</span>
                    </label>
                    <p class="mt-0.5 text-xs text-gray-400">
                      {{ t('showcase.publishModal.titleHint', { max: TITLE_MAX_LENGTH }) }}
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
                  :placeholder="t('showcase.publishModal.titlePlaceholder')"
                  class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                />
              </div>

              <div class="mb-4 grid grid-cols-2 gap-5">
                <div class="min-w-0">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('showcase.publishModal.subjectLabel') }}
                    <span class="text-red-500">*</span>
                  </label>
                  <ShowcaseFilterDropdown
                    v-model="subject"
                    block
                    variant="plain"
                    :options="subjectFilterOptions"
                    :all-label="t('showcase.publishModal.selectSubject')"
                    :include-all="false"
                  />
                </div>
                <div class="min-w-0">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('showcase.publishModal.gradeLabel') }}
                    <span class="text-red-500">*</span>
                  </label>
                  <ShowcaseFilterDropdown
                    v-model="grade"
                    block
                    variant="plain"
                    :options="gradeFilterOptions"
                    :all-label="t('showcase.publishModal.selectGrade')"
                    :include-all="false"
                  />
                </div>
              </div>

              <div v-if="isDiagramType" class="mb-4">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('showcase.publishModal.diagramTypeLabel') }}
                  <span class="text-red-500">*</span>
                </label>
                <div :class="{ 'pointer-events-none opacity-60': diagramTypeFromHistory }">
                  <ShowcaseFilterDropdown
                    v-model="diagramType"
                    block
                    variant="plain"
                    :options="diagramTypeFilterOptions"
                    :all-label="t('showcase.publishModal.selectDiagramType')"
                    :include-all="false"
                  />
                </div>
                <p v-if="diagramTypeFromHistory" class="mt-1 text-xs text-gray-400">
                  {{ t('showcase.publishModal.diagramTypeAutoMatched') }}
                </p>
              </div>

              <div v-if="!fromCanvas" class="mb-2">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('showcase.publishModal.uploadLabel') }}
                  <span
                    v-if="directFileUploadsEnabled || caseType !== 'teaching_design'"
                    class="text-red-500"
                    >*</span
                  >
                </label>
                <p
                  v-if="!directFileUploadsEnabled"
                  class="mb-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800"
                >
                  {{ t('showcase.publishModal.directUploadDisabled') }}
                </p>

                <template v-if="caseType === 'teaching_design'">
                  <label
                    class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-4 py-8 transition-colors"
                    :class="
                      directFileUploadsEnabled
                        ? 'cursor-pointer hover:border-gray-300 hover:bg-gray-50'
                        : 'pointer-events-none cursor-not-allowed opacity-50'
                    "
                  >
                    <Upload class="mb-2 h-8 w-8 text-gray-300" />
                    <span class="text-sm text-gray-500">{{ t('showcase.publishModal.uploadFile') }}</span>
                    <span class="mt-1 text-xs text-gray-400">
                      {{
                        t('showcase.publishModal.teachingDocHintWithLimit', {
                          maxMb: showcaseMaxMegabytes(CASE_TEACHING_DOC_MAX_BYTES),
                        })
                      }}
                    </span>
                    <input
                      type="file"
                      class="hidden"
                      :accept="uploadAccept"
                      :disabled="!directFileUploadsEnabled"
                      @change="onFileInput"
                    />
                  </label>
                </template>

                <template v-else-if="caseType === 'diagram_case'">
                  <p class="mb-2 text-xs text-gray-400">
                    {{
                      t('showcase.publishModal.galleryHint', {
                        max: DIAGRAM_GALLERY_MAX_ITEMS,
                      })
                    }}
                  </p>
                  <div class="grid grid-cols-2 gap-3">
                    <label
                      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors"
                      :class="
                        directFileUploadsEnabled && !galleryAtLimit
                          ? 'cursor-pointer hover:border-gray-300 hover:bg-gray-50'
                          : 'pointer-events-none cursor-not-allowed opacity-50'
                      "
                    >
                      <Upload class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">
                        {{ t('showcase.publishModal.uploadImages') }}
                      </span>
                      <span class="mt-1 text-[10px] text-gray-400">
                        {{ t('showcase.publishModal.diagramImageHint') }}
                      </span>
                      <input
                        type="file"
                        class="hidden"
                        multiple
                        :accept="uploadAccept"
                        :disabled="!directFileUploadsEnabled || galleryAtLimit"
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
                        {{ t('showcase.publishModal.pickHistory') }}
                      </span>
                    </button>
                  </div>
                  <div
                    v-if="galleryTotalCount > 0"
                    class="mt-3 space-y-2 rounded-xl border border-gray-100 bg-gray-50 p-3"
                  >
                    <p class="text-xs font-medium text-gray-500">
                      {{ t('showcase.publishModal.galleryCount', { count: galleryTotalCount, max: DIAGRAM_GALLERY_MAX_ITEMS }) }}
                    </p>
                    <div class="space-y-2">
                      <div
                        v-for="existing in galleryExistingImages"
                        :key="existing.path"
                        class="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2"
                      >
                        <span class="truncate text-xs text-gray-700">
                          {{ t('showcase.publishModal.galleryImageItem', { name: existing.filename }) }}
                        </span>
                        <button
                          type="button"
                          class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                          @click="removeGalleryExistingImage(galleryExistingImages.indexOf(existing))"
                        >
                          {{ t('showcase.publishModal.removeFile') }}
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
                          {{ t('showcase.publishModal.removeFile') }}
                        </button>
                      </div>
                      <div
                        v-for="draft in galleryDiagramDrafts"
                        :key="draft.id"
                        class="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-white px-3 py-2"
                      >
                        <span class="truncate text-xs text-gray-700">
                          {{ t('showcase.publishModal.galleryDiagramItem', { name: draft.title }) }}
                        </span>
                        <button
                          type="button"
                          class="shrink-0 text-xs text-gray-500 hover:text-red-500"
                          @click="removeGalleryDiagramDraft(draft.id)"
                        >
                          {{ t('showcase.publishModal.removeFile') }}
                        </button>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <div class="grid grid-cols-2 gap-3">
                    <label
                      class="flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-gray-50/50 px-3 py-6 transition-colors"
                      :class="
                        directFileUploadsEnabled
                          ? 'cursor-pointer hover:border-gray-300 hover:bg-gray-50'
                          : 'pointer-events-none cursor-not-allowed opacity-50'
                      "
                    >
                      <Upload class="mb-2 h-6 w-6 text-gray-300" />
                      <span class="text-xs text-gray-500">{{ t('showcase.publishModal.uploadFile') }}</span>
                      <span class="mt-1 text-[10px] text-gray-400">
                        {{ t('showcase.publishModal.templateFileHint') }}
                      </span>
                      <input
                        type="file"
                        class="hidden"
                        :accept="uploadAccept"
                        :disabled="!directFileUploadsEnabled"
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
                        {{ t('showcase.publishModal.pickHistory') }}
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
                    {{ t('showcase.publishModal.removeFile') }}
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
                        ? t('showcase.publishModal.teachingIntroLabel')
                        : t('showcase.publishModal.introLabel')
                    }}
                  </label>
                  <button
                    type="button"
                    class="publish-ai-badge"
                    :disabled="isGenerating"
                    @click="generateDescription"
                  >
                    <Sparkles class="h-3 w-3" />
                    {{ t('showcase.publishModal.aiGenerate') }}
                  </button>
                </div>
                <textarea
                  v-model="description"
                  rows="4"
                  maxlength="5000"
                  :placeholder="
                    caseType === 'teaching_design'
                      ? t('showcase.publishModal.teachingIntroPlaceholder')
                      : t('showcase.publishModal.introPlaceholder')
                  "
                  class="publish-field"
                />
              </div>

              <!-- 教学设计：设计亮点 + 教学反思 -->
              <template v-if="caseType === 'teaching_design'">
                <div class="mb-5">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('showcase.publishModal.highlightsLabel') }}
                  </label>
                  <textarea
                    v-model="designHighlights"
                    rows="4"
                    maxlength="5000"
                    :placeholder="t('showcase.publishModal.highlightsPlaceholder')"
                    class="publish-field"
                  />
                </div>

                <div class="mb-5">
                  <label class="mb-2 block text-sm font-medium text-gray-700">
                    {{ t('showcase.publishModal.reflectionLabel') }}
                  </label>
                  <textarea
                    v-model="teachingReflection"
                    rows="4"
                    maxlength="5000"
                    :placeholder="t('showcase.publishModal.reflectionPlaceholder')"
                    class="w-full rounded-xl border border-gray-100 px-4 py-2.5 text-sm shadow-sm outline-none focus:border-gray-200 focus:ring-2 focus:ring-gray-200/40"
                  />
                </div>
              </template>

              <!-- 图示类：课堂应用 -->
              <div v-if="isDiagramType" class="mb-5">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('showcase.publishModal.classroomAppLabel') }}
                </label>
                <textarea
                  v-model="classroomApplication"
                  rows="4"
                  maxlength="5000"
                  :placeholder="t('showcase.publishModal.classroomAppPlaceholder')"
                  class="publish-field"
                />
              </div>

              <!-- 标签（pill 逐个添加） -->
              <div class="mb-4">
                <label class="mb-2 block text-sm font-medium text-gray-700">
                  {{ t('showcase.publishModal.tagsLabel') }}
                  <span class="ml-1 text-xs font-normal text-gray-400">
                    {{ t('showcase.publishModal.tagCountHint', { max: TAG_MAX_COUNT }) }}
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
                  {{ t('showcase.publishModal.tagRecommended') }}
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
                    :placeholder="t('showcase.publishModal.tagInputPlaceholder')"
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
                    {{ t('showcase.publishModal.tagAdd') }}
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
                {{ t('admin.showcase.proxyAutoApprove') }}
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
              {{ t('showcase.publishModal.prev') }}
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
                  ? t('showcase.publishModal.parsingMg')
                  : t('showcase.publishModal.next')
              }}
            </button>
            <button
              v-else
              type="button"
              class="inline-flex items-center justify-center gap-2 rounded-xl bg-gray-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSubmitting"
              @click="submit"
            >
              <Loader2
                v-if="isSubmitting"
                class="h-4 w-4 shrink-0 animate-spin"
                aria-hidden="true"
              />
              <span class="max-w-[16rem] truncate">{{ submitButtonLabel }}</span>
            </button>
          </div>
        </div>
        </div>
      </div>
    </div>
  </Teleport>

  <ShowcaseHistoryDiagramPicker
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
