<script setup lang="ts">
import { Sparkles, X } from '@lucide/vue'

import LlmPhaseRing from '@/components/shared/LlmPhaseRing.vue'
import type { ShowcaseCaseType } from '@/components/showcase/showcaseShared'
import { useLanguage } from '@/composables'
import type { ModelLoadPhase } from '@/stores/llmResults'

import './PublishShowcaseModal.css'

const description = defineModel<string>('description', { required: true })
const designHighlights = defineModel<string>('designHighlights', { required: true })
const teachingReflection = defineModel<string>('teachingReflection', { required: true })
const classroomApplication = defineModel<string>('classroomApplication', { required: true })
const tagDraft = defineModel<string>('tagDraft', { required: true })
const autoApprove = defineModel<boolean>('autoApprove', { required: true })

defineProps<{
  caseType: ShowcaseCaseType
  isDiagramType: boolean
  isGenerating: boolean
  aiGeneratePhase: ModelLoadPhase
  tags: string[]
  recommendedTags: string[]
  tagsAtLimit: boolean
  canAutoApprove?: boolean
  tagMaxCount: number
  tagMaxLength: number
}>()

const emit = defineEmits<{
  generateDescription: []
  markDescriptionDirty: []
  markDesignHighlightsDirty: []
  markClassroomApplicationDirty: []
  pickRecommendedTag: [tag: string]
  removeTag: [index: number]
  addTag: []
  tagKeydown: [event: KeyboardEvent]
}>()

const { t } = useLanguage()
</script>

<template>
  <div>
    <div class="mb-5">
      <div class="mb-2 flex items-center gap-2">
        <label class="text-sm font-medium text-gray-700">
          {{
            caseType === 'teaching_design'
              ? t('showcase.publishModal.teachingIntroLabel')
              : t('showcase.publishModal.introLabel')
          }}
        </label>
        <LlmPhaseRing
          v-if="caseType === 'teaching_design' || isDiagramType"
          :phase="aiGeneratePhase"
          streaming-variant="qwen"
          border-radius="0.375rem"
          ring-padding="2px"
        >
          <button
            type="button"
            class="publish-ai-badge"
            :class="{
              loading:
                isGenerating ||
                aiGeneratePhase === 'sending' ||
                aiGeneratePhase === 'waiting' ||
                aiGeneratePhase === 'streaming',
              'phase-sending': aiGeneratePhase === 'sending',
              'phase-waiting': aiGeneratePhase === 'waiting',
              'phase-streaming': aiGeneratePhase === 'streaming',
            }"
            @click="emit('generateDescription')"
          >
            <Sparkles class="h-3 w-3" />
            {{
              isGenerating ||
              aiGeneratePhase === 'sending' ||
              aiGeneratePhase === 'waiting' ||
              aiGeneratePhase === 'streaming'
                ? t('showcase.publishModal.aiGenerateStop')
                : t('showcase.publishModal.aiGenerate')
            }}
          </button>
        </LlmPhaseRing>
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
        @input="emit('markDescriptionDirty')"
      />
    </div>

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
          @input="emit('markDesignHighlightsDirty')"
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

    <div
      v-if="isDiagramType"
      class="mb-5"
    >
      <label class="mb-2 block text-sm font-medium text-gray-700">
        {{ t('showcase.publishModal.classroomAppLabel') }}
      </label>
      <textarea
        v-model="classroomApplication"
        rows="4"
        maxlength="5000"
        :placeholder="t('showcase.publishModal.classroomAppPlaceholder')"
        class="publish-field"
        @input="emit('markClassroomApplicationDirty')"
      />
    </div>

    <div class="mb-4">
      <label class="mb-2 block text-sm font-medium text-gray-700">
        {{ t('showcase.publishModal.tagsLabel') }}
        <span class="ml-1 text-xs font-normal text-gray-400">
          {{ t('showcase.publishModal.tagCountHint', { max: tagMaxCount }) }}
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
            @click="emit('removeTag', index)"
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
          @click="emit('pickRecommendedTag', tag)"
        >
          {{ tag }}
        </button>
      </div>
      <div class="mb-1 flex items-center justify-end">
        <span
          :class="[
            'text-xs tabular-nums',
            tagDraft.length >= tagMaxLength ? 'text-amber-500' : 'text-gray-400',
          ]"
        >
          {{ tagDraft.length }}/{{ tagMaxLength }}
        </span>
      </div>
      <div class="flex gap-2">
        <input
          v-model="tagDraft"
          type="text"
          :maxlength="tagMaxLength"
          :placeholder="t('showcase.publishModal.tagInputPlaceholder')"
          class="publish-field min-w-0 flex-1"
          :disabled="tagsAtLimit"
          @keydown="emit('tagKeydown', $event)"
        />
        <button
          type="button"
          class="publish-tag-add shrink-0 rounded-xl border border-gray-100 bg-white px-4 py-2.5 text-sm text-gray-700 shadow-sm hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="tagsAtLimit"
          @click="emit('addTag')"
        >
          {{ t('showcase.publishModal.tagAdd') }}
        </button>
      </div>
    </div>

    <label
      v-if="canAutoApprove"
      class="mb-4 flex cursor-pointer items-center gap-2 text-sm text-gray-700"
    >
      <input
        v-model="autoApprove"
        type="checkbox"
      />
      {{ t('admin.showcase.proxyAutoApprove') }}
    </label>
  </div>
</template>
