<script setup lang="ts">
/**
 * Plays a slide's voice and a quieter music bed. The next slide replaces both.
 */
import { nextTick, ref, watch } from 'vue'

import type { TrainingCourseStep } from '@/types/training'

const MUSIC_VOLUME = 0.35

const props = withDefaults(
  defineProps<{
    step: TrainingCourseStep | null
    /** Music bed. The voiceover itself is spoken by the glasses. */
    autoplay?: boolean
    voiceAutoplay?: boolean
  }>(),
  { autoplay: true, voiceAutoplay: false }
)

const emit = defineEmits<{
  playing: [value: boolean]
}>()

const voiceRef = ref<HTMLAudioElement | null>(null)
const musicRef = ref<HTMLAudioElement | null>(null)

function onVoiceEnded(): void {
  const voice = voiceRef.value
  if (voice) voice.currentTime = 0
  emit('playing', false)
}

async function toggleVoice(): Promise<void> {
  const voice = voiceRef.value
  if (!voice || !props.step?.voice_url) return
  if (!voice.paused) {
    voice.pause()
    voice.currentTime = 0
    return
  }
  try {
    await voice.play()
  } catch {
    voice.pause()
  }
}

defineExpose({ toggleVoice })

async function start(): Promise<void> {
  await nextTick()
  const voice = voiceRef.value
  const music = musicRef.value
  if (props.voiceAutoplay && voice && props.step?.voice_url) {
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

function quiet(): void {
  const voice = voiceRef.value
  if (voice) {
    voice.pause()
    voice.currentTime = 0
  }
  const music = musicRef.value
  if (music) {
    music.pause()
    music.currentTime = 0
  }
  emit('playing', false)
}

watch(
  () =>
    `${props.step?.id ?? ''}|${props.step?.voice_url ?? ''}|${props.step?.music_url ?? ''}|${props.autoplay}`,
  () => {
    if (!props.autoplay) {
      quiet()
      return
    }
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
    @play="emit('playing', true)"
    @pause="emit('playing', false)"
    @ended="onVoiceEnded"
  />
  <audio
    v-if="step?.music_url"
    ref="musicRef"
    :src="step.music_url"
    loop
    preload="auto"
  />
</template>
