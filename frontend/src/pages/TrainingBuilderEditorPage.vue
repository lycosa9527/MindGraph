<script setup lang="ts">
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import TrainingBuilderFilmstrip from '@/components/training/TrainingBuilderFilmstrip.vue'
import TrainingBuilderHeader from '@/components/training/TrainingBuilderHeader.vue'
import TrainingBuilderInfoDialog from '@/components/training/TrainingBuilderInfoDialog.vue'
import TrainingBuilderNotes from '@/components/training/TrainingBuilderNotes.vue'
import TrainingBuilderStage from '@/components/training/TrainingBuilderStage.vue'
import TrainingBuilderToolbar from '@/components/training/TrainingBuilderToolbar.vue'
import TrainingTeacherPreview from '@/components/training/TrainingTeacherPreview.vue'
import { useLanguage } from '@/composables'
import { useTrainingBuilderSession } from '@/composables/training/useTrainingBuilderSession'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

const { t } = useLanguage()
const builder = useTrainingBuilderStore()
const {
  steps,
  selected,
  busy,
  infoOpen,
  previewing,
  previewFree,
  thumbs,
  current,
  stageThumb,
  hibernated,
  previewCanPrev,
  previewCanNext,
} = storeToRefs(builder)

const title = computed({
  get: () => builder.title,
  set: (value: string) => builder.setTitle(value),
})
const description = computed({
  get: () => builder.description,
  set: (value: string) => builder.setDescription(value),
})

const {
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
} = useTrainingBuilderSession()

const syncLabel = computed(() => {
  if (syncState.value === 'saving') return t('training.builder.autosaving')
  if (syncState.value === 'saved') return t('training.builder.autosaved')
  return ''
})
</script>

<template>
  <div class="training-page">
    <TrainingBuilderHeader
      :current="t('training.builder')"
      show-save
      :busy="busy"
      :previewing="previewing"
      :sync-label="syncLabel"
      @save="save"
      @info="builder.setInfoOpen(true)"
      @preview="builder.togglePreview()"
    />
    <TrainingBuilderInfoDialog
      v-model:open="infoOpen"
      v-model:title="title"
      v-model:description="description"
      :busy="busy"
      @cover="onUpload('cover', $event)"
      @save="save"
    />
    <div class="editor">
      <TrainingBuilderFilmstrip
        :steps="steps"
        :selected="selected"
        :thumbs="thumbs"
        :busy="busy"
        @select="selectStep"
        @add="addSlide"
        @images="addImageSlides"
        @remove="removeStep"
      />
      <section
        v-if="current"
        class="editor__main"
      >
        <TrainingBuilderToolbar
          :step="current"
          @awake="builder.wake()"
          @page="builder.applyCurrentPage($event)"
          @text="onAddText"
          @emoji="builder.addCurrentOverlay('emoji', { glyph: $event })"
          @arrow="builder.addCurrentOverlay('arrow', $event)"
          @spotlight="builder.addCurrentOverlay('spotlight')"
          @role="builder.addCurrentOverlay('role', { role: $event })"
          @image="onUpload('slide', $event)"
        />
        <TrainingBuilderStage
          :step="current"
          :index="selected"
          :thumb="stageThumb"
          :hibernated="hibernated"
          @wake="builder.wake()"
          @topics="onTopicsDrop"
        />
        <TrainingBuilderNotes :step="current" />
      </section>
      <TrainingTeacherPreview
        v-if="previewing && current"
        :step="current"
        :can-prev="previewCanPrev"
        :can-next="previewCanNext"
        :free="previewFree"
        @close="builder.setPreviewing(false)"
        @prev="previewMove(-1)"
        @next="previewMove(1)"
        @free="builder.togglePreviewFree()"
      />
    </div>
  </div>
</template>

<style scoped>
.training-page {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #fafaf9;
}
.editor {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
}
.editor__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.85rem 1rem 1rem;
}
</style>
