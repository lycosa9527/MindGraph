<script setup lang="ts">
/**
 * Plays a slide's voice and a quieter music bed. The next slide replaces both.
 */
import { nextTick, ref, watch } from 'vue'

import type { TrainingCourseStep } from '@/types/training'

const MUSIC_VOLUME = 0.35

const props = defineProps<{
  step: TrainingCourseStep | null
}>()

const voiceRef = ref<HTMLAudioElement | null>(null)
const musicRef = ref<HTMLAudioElement | null>(null)

async function start(): Promise<void> {
  await nextTick()
  const voice = voiceRef.value
  const music = musicRef.value
  if (voice && props.step?.voice_url) {
    voice.volume = 1
    voice.currentTime = 0
    try {
      await voice.play()
    } catch {
      voice.pause()
    }
  }
  if (music && props.step?.music_url) {
    music.volume = MUSIC_VOLUME
    music.currentTime = 0
    try {
      await music.play()
    } catch {
      music.pause()
    }
  }
}

watch(
  () => [props.step?.id, props.step?.voice_url, props.step?.music_url] as const,
  () => {
    void start()
  },
  { immediate: true }
)
</script>

<template>
  <audio
    v-if="step?.voice_url"
    ref="voiceRef"
    :src="step.voice_url"
    preload="auto"
  />
  <audio
    v-if="step?.music_url"
    ref="musicRef"
    :src="step.music_url"
    loop
    preload="auto"
  />
</template>
