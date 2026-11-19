<script setup lang="ts">
/**
 * How a slide plays after the glasses scan it: entrance, highlight, and the gap.
 */
import { computed, ref, watch } from 'vue'

import { Check, Play, Sparkles, X } from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'

type GlassesReveal = '' | 'clockwise' | 'highlight' | 'stages'

const props = defineProps<{
  open: boolean
  reveal: GlassesReveal
  pace: number
  diagramType?: string | null
}>()

const emit = defineEmits<{
  close: []
  apply: [value: { reveal: GlassesReveal; pace: number }]
  preview: [value: { reveal: GlassesReveal; pace: number }]
}>()

const { t } = useLanguage()
const mode = ref<GlassesReveal>('')
const gap = ref(280)
const visible = computed({
  get: () => props.open,
  set: (value: boolean) => {
    if (!value) emit('close')
  },
})

const revealOptions = computed(() => {
  const entrance =
    props.diagramType === 'double_bubble_map'
      ? { value: 'stages' as const, labelKey: 'sidebar.diagramType.double_bubble_map' }
      : { value: 'clockwise' as const, labelKey: 'training.builder.glassRevealClockwise' }
  return [
    { value: '' as const, labelKey: 'training.builder.glassRevealOff' },
    entrance,
    { value: 'highlight' as const, labelKey: 'training.builder.glassRevealHighlight' },
  ]
})

const seconds = computed(() => (gap.value / 1000).toFixed(1))

watch(
  () => props.open,
  (on) => {
    if (!on) return
    mode.value =
      props.diagramType === 'double_bubble_map' && props.reveal === 'clockwise'
        ? 'stages'
        : props.reveal
    gap.value = props.pace
  }
)

function onGap(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  gap.value = Number(target.value)
}

function draft(): { reveal: GlassesReveal; pace: number } {
  return { reveal: mode.value, pace: gap.value }
}
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('training.builder.ribbonGlass')"
    ribbon-key="training.builder.ribbonGlass"
    :title="t('training.builder.glassAnim')"
    title-key="training.builder.glassAnim"
    :line1="t('training.builder.glassReveal')"
    line1-key="training.builder.glassReveal"
    :icon="Sparkles"
    width="min(440px, 92vw)"
  >
    <div class="swiss-glass-stack">
      <AdminSwissSegmented
        v-model="mode"
        block
        :options="revealOptions"
        :aria-label="t('training.builder.glassAnim')"
      />
      <label class="swiss-glass-field">
        <span class="swiss-glass-field__kicker">
          <I18nText k="training.builder.glassPace" />
          {{ seconds }}s
        </span>
        <input
          class="anim-modal__range"
          type="range"
          min="160"
          max="800"
          step="40"
          :value="gap"
          :disabled="!mode"
          @input="onGap"
        />
      </label>
    </div>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="emit('close')"
        >
          <X
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="common.cancel" />
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          :disabled="!mode"
          @click="emit('preview', draft())"
        >
          <Play
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="training.builder.glassPreview" />
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="emit('apply', draft())"
        >
          <Check
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="training.builder.glassDone" />
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.anim-modal__range {
  width: 100%;
  accent-color: #1c1917;
}
.anim-modal__range:disabled {
  opacity: 0.4;
}
</style>
