<script setup lang="ts">
/**
 * This slide's voiceover auto-plays. The glasses speak it.
 */
import { Play, Square } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  playing: boolean
  aside: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const { t } = useLanguage()
</script>

<template>
  <button
    type="button"
    class="voice-glasses"
    :class="{ 'is-playing': playing, 'voice-glasses--aside': aside }"
    :aria-pressed="playing"
    :aria-label="playing ? t('training.stop') : t('training.builder.glassReveal')"
    :title="t('training.builder.glassVoiceover')"
    @pointerdown.stop
    @click.stop="emit('toggle')"
  >
    <span
      class="voice-glasses__lens"
      aria-hidden="true"
    >
      <Square
        v-if="playing"
        :size="13"
      />
      <Play
        v-else
        :size="13"
      />
    </span>
    <span
      class="voice-glasses__bridge"
      aria-hidden="true"
    />
    <span class="voice-glasses__lens voice-glasses__lens--read">
      <I18nText k="training.builder.glassVoiceover" />
    </span>
  </button>
</template>

<style scoped>
.voice-glasses {
  position: absolute;
  top: 0.45rem;
  left: 0.45rem;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 0;
  margin: 0;
  padding: 0.22rem;
  border: 2px solid #1c1917;
  border-radius: 0.85rem;
  background: rgb(255 255 255 / 0.94);
  box-shadow: 0 8px 18px rgb(28 25 23 / 0.12);
  color: #1c1917;
  cursor: pointer;
  pointer-events: auto;
}
.voice-glasses--aside {
  left: 2.85rem;
}
.voice-glasses__lens {
  display: grid;
  min-width: 1.7rem;
  height: 1.45rem;
  place-items: center;
  border: 1.5px solid #1c1917;
  border-radius: 0.55rem;
  background: #fafaf9;
}
.voice-glasses__lens--read {
  padding: 0 0.45rem;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.01em;
}
.voice-glasses__bridge {
  width: 0.45rem;
  height: 2px;
  background: #1c1917;
}
.voice-glasses.is-playing .voice-glasses__lens {
  border-color: #2563eb;
  background: #eff6ff;
  color: #2563eb;
}
.voice-glasses.is-playing .voice-glasses__bridge {
  background: #2563eb;
}
.voice-glasses.is-playing {
  border-color: #2563eb;
}
</style>
