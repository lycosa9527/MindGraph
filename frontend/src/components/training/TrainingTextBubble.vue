<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import { AlignCenter, AlignLeft, AlignRight, Bold, Italic, Minus, Plus } from '@lucide/vue'

import TrainingTextColorField from '@/components/training/TrainingTextColorField.vue'
import { useLanguage } from '@/composables'
import {
  TRAINING_TEXT_SIZE_STEP,
  textBubbleAlign,
  textBubbleBox,
  textBubbleDragReady,
  textBubbleFaceStyle,
  textBubbleFontSize,
  textBubbleInk,
  textBubbleIsBold,
  textBubbleIsItalic,
  textBubbleStroke,
} from '@/config/trainingTextBubbles'
import type { TrainingStepOverlay, TrainingTextAlign } from '@/types/training'

const props = defineProps<{
  overlay: TrainingStepOverlay
  editable?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  drag: [event: PointerEvent]
  resize: [event: PointerEvent]
  select: []
  edit: [text: string]
  bumpFont: [delta: number]
  toggleBold: []
  toggleItalic: []
  align: [align: TrainingTextAlign]
  ink: [color: string]
  stroke: [color: string]
}>()

const { t } = useLanguage()
const editorRef = ref<HTMLTextAreaElement | null>(null)
const colorPanel = ref<'ink' | 'stroke' | null>(null)
let pendingDrag: { id: number; x: number; y: number } | null = null

async function focusEditor(): Promise<void> {
  if (!props.editable || !props.selected) return
  await nextTick()
  editorRef.value?.focus()
}

onMounted(() => {
  void focusEditor()
})

watch(
  () => props.selected,
  (selected) => {
    if (!selected) colorPanel.value = null
    void focusEditor()
  }
)

function toggleColor(kind: 'ink' | 'stroke'): void {
  colorPanel.value = colorPanel.value === kind ? null : kind
}

function onInput(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLTextAreaElement)) return
  emit('edit', target.value)
}

function onChromePointer(event: PointerEvent): void {
  if (!props.editable) return
  emit('select')
  const host = event.currentTarget
  if (event.target instanceof HTMLTextAreaElement) {
    pendingDrag = { id: event.pointerId, x: event.clientX, y: event.clientY }
    if (host instanceof Element) host.setPointerCapture(event.pointerId)
    return
  }
  pendingDrag = null
  emit('drag', event)
}

function onChromeMove(event: PointerEvent): void {
  if (!pendingDrag || event.pointerId !== pendingDrag.id) return
  if (!textBubbleDragReady(pendingDrag.x, pendingDrag.y, event.clientX, event.clientY)) return
  pendingDrag = null
  editorRef.value?.blur()
  emit('drag', event)
}

function onChromeRelease(event: PointerEvent): void {
  if (pendingDrag && event.pointerId === pendingDrag.id) pendingDrag = null
}

function onResizePointer(event: PointerEvent): void {
  event.stopPropagation()
  emit('select')
  emit('resize', event)
}
</script>

<template>
  <div
    class="text-bubble"
    :class="{ 'is-selected': selected, 'is-editable': editable }"
    :style="textBubbleBox(overlay)"
    @pointerdown="onChromePointer"
    @pointermove="onChromeMove"
    @pointerup="onChromeRelease"
    @pointercancel="onChromeRelease"
  >
    <div
      v-if="editable && selected"
      class="text-bubble__bar"
      role="toolbar"
      :aria-label="t('training.builder.toolText')"
      @pointerdown.stop
    >
      <button
        type="button"
        class="text-bubble__btn"
        :title="t('training.builder.textSmaller')"
        :aria-label="t('training.builder.textSmaller')"
        @click="emit('bumpFont', -TRAINING_TEXT_SIZE_STEP)"
      >
        <Minus :size="13" />
      </button>
      <span class="text-bubble__size">{{ textBubbleFontSize(overlay) }}</span>
      <button
        type="button"
        class="text-bubble__btn"
        :title="t('training.builder.textLarger')"
        :aria-label="t('training.builder.textLarger')"
        @click="emit('bumpFont', TRAINING_TEXT_SIZE_STEP)"
      >
        <Plus :size="13" />
      </button>
      <button
        type="button"
        class="text-bubble__btn"
        :class="{ 'is-on': textBubbleIsBold(overlay) }"
        :title="t('training.builder.textBold')"
        :aria-label="t('training.builder.textBold')"
        @click="emit('toggleBold')"
      >
        <Bold :size="13" />
      </button>
      <button
        type="button"
        class="text-bubble__btn"
        :class="{ 'is-on': textBubbleIsItalic(overlay) }"
        :title="t('training.builder.textItalic')"
        :aria-label="t('training.builder.textItalic')"
        @click="emit('toggleItalic')"
      >
        <Italic :size="13" />
      </button>
      <button
        type="button"
        class="text-bubble__btn"
        :class="{ 'is-on': textBubbleAlign(overlay) === 'left' }"
        :title="t('training.builder.textAlignLeft')"
        :aria-label="t('training.builder.textAlignLeft')"
        @click="emit('align', 'left')"
      >
        <AlignLeft :size="13" />
      </button>
      <button
        type="button"
        class="text-bubble__btn"
        :class="{ 'is-on': textBubbleAlign(overlay) === 'center' }"
        :title="t('training.builder.textAlignCenter')"
        :aria-label="t('training.builder.textAlignCenter')"
        @click="emit('align', 'center')"
      >
        <AlignCenter :size="13" />
      </button>
      <button
        type="button"
        class="text-bubble__btn"
        :class="{ 'is-on': textBubbleAlign(overlay) === 'right' }"
        :title="t('training.builder.textAlignRight')"
        :aria-label="t('training.builder.textAlignRight')"
        @click="emit('align', 'right')"
      >
        <AlignRight :size="13" />
      </button>
      <TrainingTextColorField
        kind="ink"
        :label="t('training.builder.textInk')"
        :value="textBubbleInk(overlay)"
        :open="colorPanel === 'ink'"
        @toggle="toggleColor('ink')"
        @pick="emit('ink', $event)"
      />
      <TrainingTextColorField
        kind="stroke"
        :label="t('training.builder.textStroke')"
        :value="textBubbleStroke(overlay)"
        :open="colorPanel === 'stroke'"
        @toggle="toggleColor('stroke')"
        @pick="emit('stroke', $event)"
      />
    </div>
    <textarea
      v-if="editable"
      ref="editorRef"
      class="text-bubble__face text-bubble__edit"
      :style="textBubbleFaceStyle(overlay)"
      :value="overlay.text || ''"
      :placeholder="t('training.builder.textPlaceholder')"
      @input="onInput"
    />
    <p
      v-else
      class="text-bubble__face"
      :style="textBubbleFaceStyle(overlay)"
    >
      {{ overlay.text }}
    </p>
    <span
      v-if="editable"
      class="text-bubble__handle"
      @pointerdown="onResizePointer"
    />
  </div>
</template>

<style scoped>
.text-bubble {
  position: absolute;
  z-index: 2;
  display: flex;
  max-width: none;
  box-sizing: border-box;
  padding: 0.7rem 0.7rem 0.82rem;
  transform: translate(-50%, -50%);
  border: 1.5px solid var(--bubble-stroke, #d6d3d1);
  border-radius: 1.05rem;
  background: #fffef8;
  box-shadow:
    0 8px 22px rgb(28 25 23 / 0.12),
    0 1px 0 rgb(255 255 255 / 0.8) inset;
}
.text-bubble::after {
  content: '';
  position: absolute;
  left: 1.1rem;
  bottom: -0.42rem;
  width: 0.72rem;
  height: 0.72rem;
  border-right: 1.5px solid var(--bubble-stroke, #d6d3d1);
  border-bottom: 1.5px solid var(--bubble-stroke, #d6d3d1);
  background: #fffef8;
  transform: rotate(45deg);
}
.text-bubble.is-editable {
  cursor: grab;
}
.text-bubble.is-selected {
  z-index: 4;
  outline: 2px solid #ca8a04;
  outline-offset: 2px;
}
.text-bubble__bar {
  position: absolute;
  right: 0;
  bottom: calc(100% + 0.4rem);
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 0.12rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.55rem;
  background: #fff;
  padding: 0.2rem 0.28rem;
  box-shadow: 0 8px 20px rgb(28 25 23 / 0.12);
}
.text-bubble__size {
  min-width: 1.3rem;
  color: #57534e;
  font-size: 0.68rem;
  font-weight: 650;
  text-align: center;
}
.text-bubble__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  border: 0;
  border-radius: 0.3rem;
  background: transparent;
  color: #44403c;
  cursor: pointer;
}
.text-bubble__btn:hover,
.text-bubble__btn.is-on {
  background: #fef3c7;
  color: #854d0e;
}
.text-bubble__face {
  box-sizing: border-box;
  flex: 1;
  width: 100%;
  min-height: 0;
  margin: 0;
  padding: 0.15rem 0.2rem 0.25rem;
  color: #1c1917;
  line-height: 1.35;
  white-space: pre-wrap;
  overflow: hidden;
}
.text-bubble__edit {
  resize: none;
  border: 0;
  background: transparent;
  outline: none;
  overflow: auto;
  cursor: text;
}
.text-bubble__edit::placeholder {
  color: #a8a29e;
}
.text-bubble__handle {
  position: absolute;
  right: 0.08rem;
  bottom: 0.08rem;
  z-index: 3;
  width: 0.7rem;
  height: 0.7rem;
  border: 1px solid #1c1917;
  border-radius: 2px;
  background: #fafaf9;
  cursor: nwse-resize;
}
</style>
