<script setup lang="ts">
import { computed, watch } from 'vue'

import { ElButton } from 'element-plus'

import { ChevronLeft, ChevronRight } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables'
import {
  builderDiagramNodes,
  focusBuilderDiagramNode,
} from '@/composables/training/builderDiagramBridge'
import {
  interactReadCursor,
  orderedReadNodes,
  readInteract,
  setInteractMode,
} from '@/composables/training/trainingInteract'
import type { TrainingCourseStep, TrainingInteractMode } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const emit = defineEmits<{
  awake: []
}>()

const MODES = [
  { id: 'read', label: 'training.builder.interactRead' },
  { id: 'drag', label: 'training.builder.interactDrag' },
  { id: 'quiz', label: 'training.builder.interactQuiz' },
] as const

const { t } = useLanguage()
const isCanvas = computed(() => props.step.page_key === 'canvas' || props.step.type === 'canvas')
const interact = computed(() => readInteract(props.step))
const mode = computed(() => interact.value?.mode ?? null)
const sequenceSaved = computed(() => interact.value?.sequence_saved === true)
const ordered = computed(() =>
  orderedReadNodes(builderDiagramNodes.value, readInteract(props.step)?.read_order ?? [])
)
const current = computed(() => ordered.value[interactReadCursor.value] ?? null)
const caption = computed(() => {
  const node = current.value
  if (!node) return t('training.builder.interactNoNodes')
  return `${interactReadCursor.value + 1}/${ordered.value.length} ${node.text}`
})

watch(ordered, (rows) => {
  if (interactReadCursor.value >= rows.length) interactReadCursor.value = 0
})

watch([mode, interactReadCursor, current], () => {
  if (mode.value !== 'read' || !current.value) return
  focusBuilderDiagramNode(current.value.id, props.step)
})

function modeLocked(id: TrainingInteractMode): boolean {
  return sequenceSaved.value && id !== mode.value
}

function toggle(next: TrainingInteractMode): void {
  if (modeLocked(next)) return
  emit('awake')
  setInteractMode(props.step, mode.value === next ? null : next)
  interactReadCursor.value = 0
}

function move(delta: number): void {
  const count = ordered.value.length
  if (!count) return
  interactReadCursor.value = (interactReadCursor.value + delta + count) % count
}
</script>

<template>
  <ElButton
    v-for="item in MODES"
    :key="item.id"
    size="small"
    class="admin-swiss-btn"
    :class="{ 'is-on': mode === item.id }"
    :disabled="!isCanvas || modeLocked(item.id)"
    @click="toggle(item.id)"
  >
    <I18nText :k="item.label" />
  </ElButton>
  <template v-if="isCanvas && mode === 'read'">
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="ordered.length === 0"
      :aria-label="t('training.builder.interactPrev')"
      @click="move(-1)"
    >
      <ChevronLeft
        class="builder-ribbon__icon"
        aria-hidden="true"
      />
    </ElButton>
    <span class="interact-bar__caption">{{ caption }}</span>
    <span
      v-if="sequenceSaved"
      class="interact-bar__saved"
    >
      <I18nText k="training.builder.interactPlayRead" />
    </span>
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="ordered.length === 0"
      :aria-label="t('training.builder.interactNext')"
      @click="move(1)"
    >
      <ChevronRight
        class="builder-ribbon__icon"
        aria-hidden="true"
      />
    </ElButton>
  </template>
  <span
    v-else-if="!isCanvas"
    class="interact-bar__caption"
  >
    <I18nText k="training.builder.interactCanvasOnly" />
  </span>
  <span
    v-else-if="mode === 'drag' && sequenceSaved"
    class="interact-bar__saved"
  >
    <I18nText k="training.builder.interactSequenceSaved" />
  </span>
  <span
    v-else-if="mode === 'drag'"
    class="interact-bar__caption"
  >
    <I18nText k="training.builder.interactDragHint" />
  </span>
</template>

<style scoped>
.interact-bar__caption,
.interact-bar__saved {
  max-width: 16rem;
  overflow: hidden;
  color: #4b5563;
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.interact-bar__saved {
  color: #4338ca;
}
</style>
