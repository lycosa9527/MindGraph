<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { useLanguage } from '@/composables'
import {
  draftsFromStep,
  normalizeTopicOptions,
  stepUsesDualTopics,
  topicOptionDraft,
  setTrainingTopicsDragLive,
  TRAINING_TOPIC_OPTION_MAX,
  TRAINING_TOPICS_DRAG,
} from '@/composables/training/trainingTopicOptions'
import type { TrainingCourseStep, TrainingTopicOption } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const { t } = useLanguage()
const open = ref(false)
const drafts = ref<TrainingTopicOption[]>([])
let dragged = false

const dual = computed(() => stepUsesDualTopics(props.step))
const count = computed(() => (props.step.topic_options || []).length)

function beginEdit(): void {
  if (dragged) {
    dragged = false
    return
  }
  drafts.value = draftsFromStep(props.step)
  open.value = true
}

function onDragStart(event: DragEvent): void {
  dragged = true
  open.value = false
  setTrainingTopicsDragLive(true)
  const transfer = event.dataTransfer
  if (!transfer) return
  transfer.effectAllowed = 'copy'
  transfer.setData(TRAINING_TOPICS_DRAG, '1')
  transfer.setData('text/plain', 'topics')
}

function onDragEnd(): void {
  setTrainingTopicsDragLive(false)
  window.setTimeout(() => {
    dragged = false
  }, 50)
}

function addRow(): void {
  if (drafts.value.length >= TRAINING_TOPIC_OPTION_MAX) return
  drafts.value = [...drafts.value, topicOptionDraft(drafts.value.length, dual.value)]
}

function removeRow(index: number): void {
  drafts.value = drafts.value.filter((_, row) => row !== index)
  if (!drafts.value.length) {
    drafts.value = [topicOptionDraft(0, dual.value)]
  }
}

function apply(): void {
  props.step.topic_options = normalizeTopicOptions(drafts.value, dual.value)
  open.value = false
}

watch(dual, () => {
  if (open.value) drafts.value = draftsFromStep(props.step)
})
</script>

<template>
  <div
    class="topic-panel"
    @click.stop
  >
    <ElButton
      size="small"
      class="admin-swiss-btn topic-panel__btn"
      draggable="true"
      @dragstart="onDragStart"
      @dragend="onDragEnd"
      @click="beginEdit"
    >
      {{ t('training.builder.topicChoices') }}
      <span
        v-if="count"
        class="topic-panel__count"
      >{{ count }}</span>
    </ElButton>
    <div
      v-if="open"
      class="topic-panel__sheet"
    >
      <p class="topic-panel__hint">
        {{ dual ? t('training.builder.topicDualHint') : t('training.builder.topicSingleHint') }}
      </p>
      <div
        v-for="(row, index) in drafts"
        :key="row.id || index"
        class="topic-panel__row"
      >
        <template v-if="dual">
          <input
            v-model="row.item_a"
            class="topic-panel__field"
            :placeholder="t('training.itemA')"
          >
          <input
            v-model="row.item_b"
            class="topic-panel__field"
            :placeholder="t('training.itemB')"
          >
        </template>
        <input
          v-else
          v-model="row.prompt"
          class="topic-panel__field"
          :placeholder="t('training.builder.topicSingle')"
        >
        <button
          type="button"
          class="topic-panel__remove"
          @click="removeRow(index)"
        >
          {{ t('training.builder.topicRemove') }}
        </button>
      </div>
      <div class="topic-panel__actions">
        <ElButton
          size="small"
          class="admin-swiss-btn"
          :disabled="drafts.length >= TRAINING_TOPIC_OPTION_MAX"
          @click="addRow"
        >
          {{ t('training.addOption') }}
        </ElButton>
        <ElButton
          size="small"
          class="admin-swiss-btn admin-swiss-btn--primary"
          @click="apply"
        >
          {{ t('training.builder.save') }}
        </ElButton>
      </div>
    </div>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.topic-panel {
  position: relative;
}
.topic-panel__btn {
  cursor: grab;
  user-select: none;
}
.topic-panel__count {
  min-width: 1.1rem;
  border-radius: 999px;
  background: #1c1917;
  color: #fff;
  padding: 0 0.35rem;
  font-size: 0.68rem;
  line-height: 1.2rem;
  text-align: center;
}
.topic-panel__sheet {
  position: absolute;
  top: calc(100% + 0.35rem);
  left: 0;
  z-index: 20;
  width: min(28rem, calc(100vw - 8rem));
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.75rem;
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
}
.topic-panel__hint {
  margin: 0 0 0.6rem;
  color: #78716c;
  font-size: 0.75rem;
  line-height: 1.4;
}
.topic-panel__row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.45rem;
}
.topic-panel__field {
  min-width: 7rem;
  flex: 1;
  border: 1px solid #e7e5e4;
  background: #fafaf9;
  color: #1c1917;
  padding: 0.4rem 0.55rem;
  font-size: 0.8rem;
}
.topic-panel__field:focus {
  border-color: #1c1917;
  background: #fff;
  outline: none;
}
.topic-panel__remove {
  border: 0;
  background: transparent;
  color: #78716c;
  font-size: 0.72rem;
  cursor: pointer;
}
.topic-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.4rem;
  margin-top: 0.35rem;
}
</style>
