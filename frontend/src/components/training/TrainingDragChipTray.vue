<script setup lang="ts">
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { trainingDragFilledIds } from '@/composables/training/trainingDragKnock'
import { readInteract, shuffledBlanks } from '@/composables/training/trainingInteract'
import type { TrainingCourseStep, TrainingInteractBlank } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const rows = computed(() => shuffledBlanks(readInteract(props.step)?.blanks ?? []))

function placed(nodeId: string): boolean {
  return trainingDragFilledIds.value.includes(nodeId)
}

function startDrag(blank: TrainingInteractBlank, event: DragEvent): void {
  event.dataTransfer?.setData('text/plain', blank.answer)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside
    v-if="rows.length"
    class="drag-play"
  >
    <p class="drag-play__title"><I18nText k="training.builder.interactDrag" /></p>
    <div
      v-for="row in rows"
      :key="row.node_id"
      class="drag-play__row"
      :class="{ 'is-ok': placed(row.node_id) }"
      draggable="true"
      @dragstart="startDrag(row, $event)"
    >
      <span class="drag-play__text">{{ row.answer }}</span>
    </div>
  </aside>
</template>

<style scoped>
.drag-play {
  display: flex;
  box-sizing: border-box;
  max-height: 100%;
  flex-direction: column;
  gap: 0.35rem;
  overflow: auto;
  border: 1px solid #e7e5e4;
  border-right: 0;
  border-radius: 8px 0 0 8px;
  background: rgb(255 255 255 / 0.96);
  padding: 0.6rem 0.7rem 0.8rem;
}
.drag-play__title {
  margin: 0.15rem 0 0.2rem;
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
}
.drag-play__row {
  display: flex;
  align-items: center;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  background: #fff;
  padding: 0.4rem 0.5rem;
  color: #1f2937;
  font-size: 12px;
  cursor: grab;
}
.drag-play__row.is-ok {
  border-color: #a7f3d0;
  background: #ecfdf5;
  color: #047857;
}
.drag-play__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
