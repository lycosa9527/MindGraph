<script setup lang="ts">
/**
 * Mind map slide show HUD — page indicator and auto-play toggle.
 */
import { Pause, Play } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { PRESENTATION_Z } from '@/config/uiConfig'

defineProps<{
  slideIndex: number
  slideCount: number
  slideTitle: string
  autoPlay: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleAutoPlay'): void
  (e: 'prev'): void
  (e: 'next'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div
    class="mind-map-slide-overlay pointer-events-auto fixed bottom-6 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-2xl border border-gray-200/80 bg-white/92 px-4 py-2.5 shadow-xl backdrop-blur-md dark:border-gray-600/80 dark:bg-gray-900/88"
    :style="{ zIndex: PRESENTATION_Z.TIMER_OVERLAY - 1 }"
  >
    <button
      type="button"
      class="slide-nav-btn"
      :aria-label="t('canvas.mindMapSlideOverlay.prev')"
      @click="emit('prev')"
    >
      ←
    </button>

    <div class="min-w-0 text-center">
      <p class="slide-title truncate">
        {{ slideTitle }}
      </p>
      <p class="slide-counter">
        {{ slideIndex + 1 }} / {{ slideCount }}
      </p>
    </div>

    <button
      type="button"
      class="slide-nav-btn"
      :aria-label="t('canvas.mindMapSlideOverlay.next')"
      @click="emit('next')"
    >
      →
    </button>

    <div class="mx-1 h-5 w-px bg-gray-200 dark:bg-gray-600" />

    <button
      type="button"
      class="autoplay-btn"
      :class="{ 'is-active': autoPlay }"
      @click="emit('toggleAutoPlay')"
    >
      <Pause
        v-if="autoPlay"
        class="h-4 w-4"
      />
      <Play
        v-else
        class="h-4 w-4"
      />
      <span>{{
        autoPlay
          ? t('canvas.mindMapSlideOverlay.stopAutoPlay')
          : t('canvas.mindMapSlideOverlay.startAutoPlay')
      }}</span>
    </button>
  </div>
</template>

<style scoped>
.slide-title {
  margin: 0;
  max-width: min(42vw, 280px);
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(30 41 59);
}

.slide-counter {
  margin: 0.125rem 0 0;
  font-size: 0.6875rem;
  color: rgb(100 116 139);
}

.slide-nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 0.5rem;
  background: rgb(241 245 249);
  color: rgb(51 65 85);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}

.slide-nav-btn:hover {
  background: rgb(226 232 240);
}

.autoplay-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: none;
  border-radius: 0.625rem;
  padding: 0.35rem 0.65rem;
  background: rgb(255 247 237);
  color: rgb(154 52 18);
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgb(254 215 170 / 0.95);
}

.autoplay-btn.is-active {
  background: rgb(255 237 213);
}

.dark .slide-title {
  color: rgb(241 245 249);
}

.dark .slide-counter {
  color: rgb(148 163 184);
}

.dark .slide-nav-btn {
  background: rgb(51 65 85);
  color: rgb(226 232 240);
}
</style>
