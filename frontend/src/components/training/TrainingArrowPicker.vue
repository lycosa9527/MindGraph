<script setup lang="ts">
import { ref } from 'vue'

import { useLanguage } from '@/composables'
import {
  TRAINING_ARROW_COLORS,
  TRAINING_ARROW_LINES,
  type TrainingArrowColor,
  type TrainingArrowLine,
  trainingArrowHex,
} from '@/config/trainingMarkPalettes'

const emit = defineEmits<{
  pick: [opts: { color: TrainingArrowColor; line: TrainingArrowLine }]
}>()

const { t } = useLanguage()
const color = ref<TrainingArrowColor>('red')
const line = ref<TrainingArrowLine>('solid')

const lineKeys: Record<TrainingArrowLine, string> = {
  solid: 'training.builder.arrowSolid',
  dashed: 'training.builder.arrowDashed',
  thick: 'training.builder.arrowThick',
}

function pickLine(next: TrainingArrowLine): void {
  line.value = next
  emit('pick', { color: color.value, line: next })
}

function pickColor(next: TrainingArrowColor): void {
  color.value = next
}

function dash(style: TrainingArrowLine): string | undefined {
  return style === 'dashed' ? '4 3' : undefined
}

function width(style: TrainingArrowLine): number {
  return style === 'thick' ? 3.4 : 1.8
}
</script>

<template>
  <div class="arrow-picker">
    <div
      class="arrow-picker__lines"
      role="list"
    >
      <button
        v-for="style in TRAINING_ARROW_LINES"
        :key="style"
        type="button"
        class="arrow-picker__line"
        :class="{ 'is-on': style === line }"
        :aria-label="t(lineKeys[style])"
        @click="pickLine(style)"
      >
        <svg
          viewBox="0 0 48 12"
          aria-hidden="true"
        >
          <line
            x1="3"
            y1="6"
            x2="42"
            y2="6"
            :stroke="trainingArrowHex(color)"
            :stroke-width="width(style)"
            :stroke-dasharray="dash(style)"
            stroke-linecap="round"
            :marker-end="`url(#arrow-pick-${style})`"
          />
          <defs>
            <marker
              :id="`arrow-pick-${style}`"
              markerWidth="6"
              markerHeight="6"
              refX="5"
              refY="3"
              orient="auto"
            >
              <path
                d="M0,0 L6,3 L0,6 Z"
                :fill="trainingArrowHex(color)"
              />
            </marker>
          </defs>
        </svg>
        <span>{{ t(lineKeys[style]) }}</span>
      </button>
    </div>
    <div
      class="arrow-picker__colors"
      role="list"
    >
      <button
        v-for="swatch in TRAINING_ARROW_COLORS"
        :key="swatch.key"
        type="button"
        class="arrow-picker__swatch"
        :class="{ 'is-on': swatch.key === color }"
        :style="{ background: swatch.hex }"
        :aria-label="swatch.key"
        @click="pickColor(swatch.key)"
      />
    </div>
  </div>
</template>

<style scoped>
.arrow-picker {
  display: flex;
  width: 11.5rem;
  flex-direction: column;
  gap: 0.5rem;
}
.arrow-picker__lines {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.arrow-picker__line {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.25rem 0.4rem;
  color: #57534e;
  font-size: 0.7rem;
  cursor: pointer;
}
.arrow-picker__line.is-on {
  border-color: #1c1917;
  color: #1c1917;
}
.arrow-picker__line svg {
  width: 3.2rem;
  height: 0.85rem;
}
.arrow-picker__colors {
  display: flex;
  gap: 0.3rem;
}
.arrow-picker__swatch {
  width: 1.15rem;
  height: 1.15rem;
  border: 2px solid transparent;
  border-radius: 999px;
  cursor: pointer;
}
.arrow-picker__swatch.is-on {
  border-color: #1c1917;
}
</style>
