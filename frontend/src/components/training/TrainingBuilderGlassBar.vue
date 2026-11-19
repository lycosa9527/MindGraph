<script setup lang="ts">
/**
 * Glasses tab: open the voiceover or animation dialog for this slide.
 */
import { nextTick, ref } from 'vue'

import { ElButton } from 'element-plus'

import { Mic, Sparkles } from '@lucide/vue'

import TrainingAnimationModal from '@/components/training/TrainingAnimationModal.vue'
import TrainingVoiceoverModal from '@/components/training/TrainingVoiceoverModal.vue'
import { playGlassesReveal } from '@/composables/training/glassesSlideReveal'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import { assignTrainingStepField } from '@/utils/trainingStepPatch'

const builder = useTrainingBuilderStore()
const voiceOpen = ref(false)
const animOpen = ref(false)

function onVoiceApply(value: {
  line: string
  rate: number
  asset: { id: string; url: string } | null
}): void {
  const current = builder.current
  if (!current) return
  assignTrainingStepField(current, 'glasses_line', value.line)
  assignTrainingStepField(current, 'glasses_rate', value.rate)
  if (value.asset) {
    assignTrainingStepField(current, 'voice_asset_id', value.asset.id)
    assignTrainingStepField(current, 'voice_url', value.asset.url)
  }
  builder.wake()
}

function onAnimApply(value: {
  reveal: '' | 'clockwise' | 'highlight' | 'stages'
  pace: number
}): void {
  const current = builder.current
  if (!current) return
  assignTrainingStepField(current, 'glasses_reveal', value.reveal)
  assignTrainingStepField(current, 'glasses_pace', value.pace)
  animOpen.value = false
  builder.wake()
}

async function onPreview(value: { reveal: string; pace: number }): Promise<void> {
  animOpen.value = false
  await nextTick()
  await new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve())
  })
  const stage = document.querySelector('.builder-stage')
  if (!(stage instanceof HTMLElement)) return
  void playGlassesReveal(stage, value.reveal, value.pace)
}
</script>

<template>
  <div class="builder-ribbon__tools">
    <ElButton
      size="small"
      class="admin-swiss-btn"
      @click="voiceOpen = true"
    >
      <Mic
        class="builder-ribbon__icon"
        aria-hidden="true"
      />
      <I18nText k="training.builder.glassVoiceover" />
    </ElButton>
    <ElButton
      size="small"
      class="admin-swiss-btn"
      @click="animOpen = true"
    >
      <Sparkles
        class="builder-ribbon__icon"
        aria-hidden="true"
      />
      <I18nText k="training.builder.glassAnim" />
    </ElButton>
    <TrainingVoiceoverModal
      :open="voiceOpen"
      :line="builder.current?.glasses_line || ''"
      :rate="builder.current?.glasses_rate || 1"
      :voice-url="builder.current?.voice_url || ''"
      :course-id="builder.courseId"
      @close="voiceOpen = false"
      @apply="onVoiceApply"
    />
    <TrainingAnimationModal
      :open="animOpen"
      :reveal="builder.current?.glasses_reveal || ''"
      :pace="builder.current?.glasses_pace || 280"
      :diagram-type="builder.current?.diagram_type || ''"
      @close="animOpen = false"
      @apply="onAnimApply"
      @preview="onPreview"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped src="./trainingBuilderRibbon.css"></style>
