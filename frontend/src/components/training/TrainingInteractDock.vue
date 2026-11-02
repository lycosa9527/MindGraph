<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { Check, GripVertical } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import TrainingDragHintModal from '@/components/training/TrainingDragHintModal.vue'
import TrainingInteractNodeMenu from '@/components/training/TrainingInteractNodeMenu.vue'
import { useLanguage } from '@/composables'
import {
  builderDiagramNodes,
  focusBuilderDiagramNode,
} from '@/composables/training/builderDiagramBridge'
import {
  setTrainingDragPicking,
  trainingDragPicking,
} from '@/composables/training/trainingDragKnock'
import {
  ensureQuiz,
  interactReadCursor,
  orderedReadNodes,
  readInteract,
  reorderReadIds,
  saveDragBlanks,
  saveQuiz,
  saveReadSequence,
  setDragBlankOrder,
  setInteractBlankHint,
  setReadOrder,
} from '@/composables/training/trainingInteract'
import type { TrainingCourseStep } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const emit = defineEmits<{
  awake: []
}>()

const CHOICES = ['a', 'b', 'c'] as const

const { t } = useLanguage()
const quizNodeId = ref('')
const prompt = ref('')
const labels = ref<string[]>(['', '', ''])
const correct = ref<(typeof CHOICES)[number]>('a')
const picked = ref('')

const mode = computed(() => readInteract(props.step)?.mode ?? null)
const nodes = computed(() => builderDiagramNodes.value)
const blanks = computed(() => readInteract(props.step)?.blanks ?? [])
const readOrder = computed(() =>
  orderedReadNodes(nodes.value, readInteract(props.step)?.read_order ?? [])
)
const sequenceSaved = computed(() => readInteract(props.step)?.sequence_saved === true)
const dragFrom = ref<number | null>(null)
const dragOver = ref<number | null>(null)
const skipReadClick = ref(false)

watch(
  nodes,
  (rows) => {
    if (quizNodeId.value && rows.some((node) => node.id === quizNodeId.value)) return
    quizNodeId.value = rows[0]?.id ?? ''
  },
  { immediate: true }
)

watch(quizNodeId, (nodeId) => {
  picked.value = ''
  if (!nodeId) return
  const quiz = ensureQuiz(props.step, nodeId)
  prompt.value = quiz.prompt
  labels.value = CHOICES.map((id) => quiz.choices.find((choice) => choice.id === id)?.label ?? '')
  const marked = quiz.choices.find((choice) => choice.correct)?.id
  correct.value = marked === 'b' || marked === 'c' ? marked : 'a'
})

function commitQuiz(): void {
  if (!quizNodeId.value) return
  emit('awake')
  saveQuiz(props.step, {
    node_id: quizNodeId.value,
    prompt: prompt.value,
    choices: CHOICES.map((id, index) => ({
      id,
      label: labels.value[index] ?? '',
      correct: correct.value === id,
    })),
  })
}

function pickChoice(id: (typeof CHOICES)[number]): void {
  picked.value = id
}

function chooseRead(index: number): void {
  if (skipReadClick.value) {
    skipReadClick.value = false
    return
  }
  const node = readOrder.value[index]
  if (!node) return
  interactReadCursor.value = index
  focusBuilderDiagramNode(node.id, props.step)
}

function startReadDrag(index: number, event: DragEvent): void {
  dragFrom.value = index
  event.dataTransfer?.setData('text/plain', String(index))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function overRead(index: number, event: DragEvent): void {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOver.value = index
}

function dropRead(index: number, event: DragEvent): void {
  event.preventDefault()
  const from = dragFrom.value
  dragFrom.value = null
  dragOver.value = null
  if (from === null || from === index) return
  const currentId = readOrder.value[interactReadCursor.value]?.id
  const next = reorderReadIds(
    readOrder.value.map((node) => node.id),
    from,
    index
  )
  skipReadClick.value = true
  emit('awake')
  setReadOrder(props.step, next)
  if (!currentId) return
  const nextCursor = next.indexOf(currentId)
  if (nextCursor >= 0) interactReadCursor.value = nextCursor
}

function endReadDrag(): void {
  dragFrom.value = null
  dragOver.value = null
}

function saveSequence(): void {
  if (readOrder.value.length === 0) return
  emit('awake')
  saveReadSequence(
    props.step,
    readOrder.value.map((node) => node.id)
  )
}

function saveDrag(): void {
  if (blanks.value.length === 0 || sequenceSaved.value) return
  emit('awake')
  saveDragBlanks(props.step)
}

function toggleDragPick(): void {
  setTrainingDragPicking(!trainingDragPicking.value)
}

function saveHint(payload: { nodeId: string; text: string }): void {
  emit('awake')
  setInteractBlankHint(props.step, payload.nodeId, payload.text)
}

function dropDrag(index: number, event: DragEvent): void {
  event.preventDefault()
  const from = dragFrom.value
  dragFrom.value = null
  dragOver.value = null
  if (from === null || from === index) return
  emit('awake')
  setDragBlankOrder(
    props.step,
    reorderReadIds(
      blanks.value.map((row) => row.node_id),
      from,
      index
    )
  )
}
</script>

<template>
  <aside
    v-if="mode === 'read' || mode === 'drag' || mode === 'quiz'"
    class="interact-dock"
  >
    <template v-if="mode === 'read'">
      <p class="interact-dock__title"><I18nText k="training.builder.interactRead" /></p>
      <p class="interact-dock__empty"><I18nText k="training.builder.interactReadHint" /></p>
      <p
        v-if="readOrder.length === 0"
        class="interact-dock__empty"
      >
        <I18nText k="training.builder.interactNoNodes" />
      </p>
      <div
        v-for="(node, index) in readOrder"
        :key="node.id"
        class="interact-dock__order"
        :class="{
          'is-current': index === interactReadCursor,
          'is-over': dragOver === index,
        }"
        role="button"
        tabindex="0"
        draggable="true"
        @click="chooseRead(index)"
        @keydown.enter.prevent="chooseRead(index)"
        @keydown.space.prevent="chooseRead(index)"
        @dragstart="startReadDrag(index, $event)"
        @dragover="overRead(index, $event)"
        @drop="dropRead(index, $event)"
        @dragend="endReadDrag"
      >
        <GripVertical
          class="interact-dock__grip"
          aria-hidden="true"
        />
        <span class="interact-dock__index">{{ index + 1 }}</span>
        <span class="interact-dock__order-text">{{ node.text }}</span>
        <TrainingInteractNodeMenu
          :step="step"
          :node-id="node.id"
          @awake="emit('awake')"
        />
      </div>
      <button
        type="button"
        class="interact-dock__save"
        :class="{ 'is-saved': sequenceSaved }"
        :disabled="readOrder.length === 0 || sequenceSaved"
        @click="saveSequence"
      >
        <I18nText
          :k="
            sequenceSaved
              ? 'training.builder.interactSequenceSaved'
              : 'training.builder.interactSaveSequence'
          "
        />
        <Check
          v-if="sequenceSaved"
          class="interact-dock__check"
          aria-hidden="true"
        />
      </button>
    </template>
    <template v-else-if="mode === 'drag'">
      <p class="interact-dock__title"><I18nText k="training.builder.interactDrag" /></p>
      <p class="interact-dock__empty"><I18nText k="training.builder.interactDragHint" /></p>
      <p
        v-if="blanks.length === 0"
        class="interact-dock__empty"
      >
        <I18nText k="training.builder.interactNoNodes" />
      </p>
      <div
        v-for="(blank, index) in blanks"
        :key="blank.node_id"
        class="interact-dock__order"
        :class="{ 'is-over': dragOver === index }"
        role="button"
        tabindex="0"
        draggable="true"
        @click="focusBuilderDiagramNode(blank.node_id, step)"
        @keydown.enter.prevent="focusBuilderDiagramNode(blank.node_id, step)"
        @dragstart="startReadDrag(index, $event)"
        @dragover="overRead(index, $event)"
        @drop="dropDrag(index, $event)"
        @dragend="endReadDrag"
      >
        <GripVertical
          class="interact-dock__grip"
          aria-hidden="true"
        />
        <span class="interact-dock__index">{{ index + 1 }}</span>
        <span class="interact-dock__order-text">{{ blank.answer }}</span>
        <TrainingInteractNodeMenu
          explain-only
          :step="step"
          :node-id="blank.node_id"
          @awake="emit('awake')"
        />
      </div>
      <button
        type="button"
        class="interact-dock__pick"
        :class="{ 'is-picking': trainingDragPicking }"
        @click="toggleDragPick"
      >
        <I18nText
          :k="
            trainingDragPicking
              ? 'training.builder.interactFinishPick'
              : 'training.builder.interactPickNodes'
          "
        />
      </button>
      <button
        type="button"
        class="interact-dock__save"
        :class="{ 'is-saved': sequenceSaved }"
        :disabled="blanks.length === 0 || sequenceSaved"
        @click="saveDrag"
      >
        <I18nText
          :k="
            sequenceSaved
              ? 'training.builder.interactSequenceSaved'
              : 'training.builder.interactSaveSequence'
          "
        />
        <Check
          v-if="sequenceSaved"
          class="interact-dock__check"
          aria-hidden="true"
        />
      </button>
      <TrainingDragHintModal @save="saveHint" />
    </template>
    <template v-else>
      <p class="interact-dock__title"><I18nText k="training.builder.interactQuiz" /></p>
      <select
        v-model="quizNodeId"
        class="interact-dock__field"
        @change="focusBuilderDiagramNode(quizNodeId, step)"
      >
        <option
          v-for="node in nodes"
          :key="node.id"
          :value="node.id"
        >
          {{ node.text }}
        </option>
      </select>
      <label class="interact-dock__label">
        <I18nText k="training.builder.interactQuizPrompt" />
        <input
          v-model="prompt"
          class="interact-dock__field"
          type="text"
          @change="commitQuiz"
        />
      </label>
      <label
        v-for="(choiceId, index) in CHOICES"
        :key="choiceId"
        class="interact-dock__label"
      >
        <span>
          <input
            v-model="correct"
            type="radio"
            :value="choiceId"
            @change="commitQuiz"
          />
          <I18nText
            k="training.builder.interactOption"
            :params="{ n: choiceId.toUpperCase() }"
          />
        </span>
        <input
          v-model="labels[index]"
          class="interact-dock__field"
          type="text"
          @change="commitQuiz"
        />
      </label>
      <p class="interact-dock__title"><I18nText k="training.builder.interactTry" /></p>
      <p class="interact-dock__prompt">
        <template v-if="prompt">{{ prompt }}</template
        ><I18nText
          v-else
          k="training.builder.interactQuizPrompt"
        />
      </p>
      <button
        v-for="(choiceId, index) in CHOICES"
        :key="`try-${choiceId}`"
        type="button"
        class="interact-dock__choice"
        :class="{
          'is-ok': picked === choiceId && picked === correct,
          'is-bad': picked === choiceId && picked !== correct,
        }"
        @click="pickChoice(choiceId)"
      >
        {{ choiceId.toUpperCase() }}. {{ labels[index] }}
      </button>
    </template>
  </aside>
</template>

<style scoped>
.interact-dock {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 4300;
  display: flex;
  width: var(--builder-dock-width, min(16rem, 42%));
  flex-direction: column;
  gap: 0.35rem;
  overflow: auto;
  border-left: 1px solid #e7e5e4;
  background: rgb(255 255 255 / 0.96);
  padding: 0.6rem 0.7rem 0.8rem;
}
.interact-dock__title {
  margin: 0.35rem 0 0;
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
}
.interact-dock__empty,
.interact-dock__prompt,
.interact-dock__sheet {
  margin: 0;
  color: #4b5563;
  font-size: 12px;
}
.interact-dock__node,
.interact-dock__label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: #374151;
  font-size: 12px;
}
.interact-dock__label {
  flex-direction: column;
  align-items: stretch;
}
.interact-dock__field,
.interact-dock__chip,
.interact-dock__slot,
.interact-dock__choice {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  background: #fff;
  color: #1f2937;
  font-size: 12px;
}
.interact-dock__field {
  padding: 0.3rem 0.4rem;
}
.interact-dock__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}
.interact-dock__chip {
  width: auto;
  padding: 0.25rem 0.45rem;
  cursor: grab;
}
.interact-dock__slot,
.interact-dock__choice {
  padding: 0.4rem 0.5rem;
  text-align: start;
  cursor: pointer;
}
.interact-dock__sheet {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
}
.interact-dock__sheet.is-ok,
.interact-dock__choice.is-ok {
  color: #047857;
}
.interact-dock__sheet.is-bad,
.interact-dock__choice.is-bad {
  color: #b91c1c;
}
.interact-dock__order {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
  border: 1px solid #e7e5e4;
  border-radius: 6px;
  background: #fff;
  padding: 0.35rem 0.4rem;
  color: #1f2937;
  font-size: 12px;
  text-align: start;
  cursor: grab;
}
.interact-dock__order.is-current {
  border-color: #6366f1;
  background: #eef2ff;
}
.interact-dock__order.is-over {
  border-color: #f43f5e;
}
.interact-dock__grip {
  width: 14px;
  height: 14px;
  flex: none;
  color: #9ca3af;
}
.interact-dock__index {
  flex: none;
  width: 1.1rem;
  color: #6b7280;
  font-weight: 700;
}
.interact-dock__order-text {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.interact-dock__pick,
.interact-dock__save {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  border: 0;
  border-radius: 6px;
  padding: 0.45rem 0.5rem;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}
.interact-dock__pick {
  margin-top: auto;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
}
.interact-dock__pick.is-picking {
  border-color: #e7e5e4;
  background: #fff;
  color: #374151;
}
.interact-dock__save {
  background: #4f46e5;
  color: #fff;
}
.interact-dock__save:disabled {
  background: #e5e7eb;
  color: #6b7280;
  cursor: default;
}
.interact-dock__save.is-saved {
  justify-content: space-between;
  background: #ecfdf5;
  color: #047857;
}
.interact-dock__save.is-saved:disabled {
  background: #ecfdf5;
  color: #047857;
}
.interact-dock__check {
  width: 16px;
  height: 16px;
  flex: none;
  color: #059669;
}
</style>
