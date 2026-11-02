<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { PanelLeftOpen } from '@lucide/vue'

import TrainingBuilderFilmstrip from '@/components/training/TrainingBuilderFilmstrip.vue'
import TrainingBuilderInfoDialog from '@/components/training/TrainingBuilderInfoDialog.vue'
import TrainingBuilderNotes from '@/components/training/TrainingBuilderNotes.vue'
import TrainingBuilderStage from '@/components/training/TrainingBuilderStage.vue'
import TrainingBuilderToolbar from '@/components/training/TrainingBuilderToolbar.vue'
import TrainingTeacherPreview from '@/components/training/TrainingTeacherPreview.vue'
import { useLanguage } from '@/composables'
import {
  builderDiagramSession,
  focusBuilderDiagramNode,
  isBoundToStep,
} from '@/composables/training/builderDiagramBridge'
import { readFocusNodeId } from '@/composables/training/trainingInteract'
import { useTrainingBuilderSession } from '@/composables/training/useTrainingBuilderSession'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

const { t } = useLanguage()
const builder = useTrainingBuilderStore()
const railCollapsed = ref(false)
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
const menuLabel = computed({
  get: () => builder.menuLabel,
  set: (value: string) => builder.setMenuLabel(value),
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
  onLockArm,
  onLock,
  saveLabel,
  saveTone,
} = useTrainingBuilderSession()

function fitPlayCanvas(): void {
  const step = builder.current
  const nodeId = step ? readFocusNodeId(step) : null
  if (nodeId) {
    focusBuilderDiagramNode(nodeId, step)
    return
  }
  if (!isBoundToStep(step)) return
  builderDiagramSession.value?.viewBus.emit('view:fit_to_canvas_requested', {
    animate: true,
    userInitiated: true,
  })
}

watch(previewing, (on) => {
  if (!on) return
  fitPlayCanvas()
})

function onVodResize(size: { width: number; height: number }): void {
  const step = builder.current
  if (!step) return
  step.vod_width = size.width
  step.vod_height = size.height
}
</script>

<template>
  <div
    class="training-page"
    :class="{ 'training-page--play': previewing }"
  >
    <TrainingBuilderToolbar
      v-if="current"
      v-show="!previewing"
      :step="current"
      :previewing="previewing"
      :save-label="saveLabel"
      :save-tone="saveTone"
      @awake="builder.wake()"
      @page="builder.applyCurrentPage($event)"
      @text="onAddText"
      @emoji="builder.addCurrentOverlay('emoji', { glyph: $event })"
      @arrow="builder.addCurrentOverlay('arrow', $event)"
      @spotlight="builder.addCurrentOverlay('spotlight')"
      @role="builder.addCurrentOverlay('role', { role: $event })"
      @role-asset="
        builder.addCurrentOverlay('role', {
          asset_id: $event.id,
          src: $event.url,
          x: 88,
          y: 64,
        })
      "
      @image="onUpload('slide', $event)"
      @lock-arm="onLockArm"
      @lock="onLock(selected)"
      @save="save"
      @info="builder.setInfoOpen(true)"
      @preview="builder.togglePreview()"
    />
    <TrainingBuilderInfoDialog
      v-model:open="infoOpen"
      v-model:title="title"
      v-model:description="description"
      v-model:menu-label="menuLabel"
      :busy="busy"
      @cover="onUpload('cover', $event)"
      @save="save"
    />
    <div class="editor">
      <TrainingBuilderFilmstrip
        v-show="!previewing"
        :collapsed="railCollapsed"
        :steps="steps"
        :selected="selected"
        :thumbs="thumbs"
        :busy="busy"
        @select="selectStep"
        @add="addSlide"
        @images="addImageSlides"
        @remove="removeStep"
        @lock-arm="onLockArm"
        @lock="onLock"
        @update:collapsed="railCollapsed = $event"
      />
      <section
        v-if="current"
        class="editor__main"
      >
        <TrainingBuilderStage
          :step="current"
          :index="selected"
          :thumb="stageThumb"
          :hibernated="hibernated"
          :playing="previewing"
          :play-audio="!previewing || current.page_key === 'canvas' || current.type === 'canvas'"
          :can-next="previewCanNext"
          @wake="builder.wake()"
          @topics="onTopicsDrop"
          @resize="onVodResize"
          @next="previewMove(1)"
        />
        <TrainingBuilderNotes
          v-show="!previewing"
          :step="current"
        >
          <template
            v-if="railCollapsed"
            #lead
          >
            <button
              type="button"
              class="editor__rail"
              :title="t('training.builder.expandSlides')"
              :aria-label="t('training.builder.expandSlides')"
              aria-expanded="false"
              @click="railCollapsed = false"
            >
              <PanelLeftOpen
                :size="18"
                aria-hidden="true"
              />
            </button>
          </template>
        </TrainingBuilderNotes>
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
        @resize="onVodResize"
        @mode="builder.setPreviewFree($event === 'free')"
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
.training-page--play {
  position: fixed;
  inset: 0;
  z-index: 70;
  background: #f8fafc;
}
.training-page--play .editor__main {
  gap: 0;
  padding: 0;
}
.editor {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
}
.editor__rail {
  display: flex;
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #57534e;
  cursor: pointer;
}
.editor__rail:hover {
  background: #f5f5f4;
  color: #1c1917;
}
.editor__main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.85rem 1rem 1rem;
}
@media (max-width: 768px) {
  .editor {
    flex-direction: column;
  }
}
</style>
