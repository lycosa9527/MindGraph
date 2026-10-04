<script setup lang="ts">
/**
 * Per-slide voice or music upload. The native player is ready as soon as the file lands.
 */
import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

const props = defineProps<{
  kind: 'voice' | 'music'
}>()

const { t } = useLanguage()
const notify = useNotifications()
const builder = useTrainingBuilderStore()
const busy = ref(false)

const accept = 'audio/mpeg,audio/mp4,audio/wav,audio/webm,.mp3,.m4a,.wav,.webm'

function url(): string {
  const step = builder.current
  if (!step) return ''
  return props.kind === 'voice' ? step.voice_url || '' : step.music_url || ''
}

function labelKey(): string {
  return props.kind === 'voice' ? 'training.builder.voice' : 'training.builder.music'
}

function removeKey(): string {
  return props.kind === 'voice' ? 'training.builder.voiceRemove' : 'training.builder.musicRemove'
}

function clear(): void {
  const step = builder.current
  if (!step) return
  builder.wake()
  if (props.kind === 'voice') {
    step.voice_asset_id = null
    step.voice_url = null
    return
  }
  step.music_asset_id = null
  step.music_url = null
}

async function onFile(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const file = input.files?.[0]
  input.value = ''
  if (!file || !builder.courseId) return
  busy.value = true
  builder.wake()
  try {
    const uploaded = await uploadTrainingFile(builder.courseId, props.kind, file)
    const step = builder.current
    if (!step) return
    if (props.kind === 'voice') {
      step.voice_asset_id = uploaded.id
      step.voice_url = uploaded.url
    } else {
      step.music_asset_id = uploaded.id
      step.music_url = uploaded.url
    }
  } catch {
    notify.errorKey('training.builder.uploadFailed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <label class="slide-audio">
    <span class="slide-audio__label"><I18nText :k="labelKey()" /></span>
    <input
      type="file"
      :accept="accept"
      :disabled="busy"
      :aria-label="t(labelKey())"
      @change="onFile"
    />
    <audio
      v-if="url()"
      class="slide-audio__play"
      :src="url()"
      controls
      preload="none"
    />
    <button
      v-if="url()"
      type="button"
      class="slide-audio__remove"
      :aria-label="t(removeKey())"
      @click.prevent="clear"
    >
      <I18nText :k="removeKey()" />
    </button>
  </label>
</template>

<style scoped>
.slide-audio {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #44403c;
  font-size: 0.75rem;
}
.slide-audio__label {
  font-weight: 650;
}
.slide-audio__play {
  width: 9.5rem;
  height: 1.7rem;
}
.slide-audio__remove {
  border: 0;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  font-size: 0.72rem;
}
</style>
