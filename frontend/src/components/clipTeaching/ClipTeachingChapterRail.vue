<script setup lang="ts">
import { computed } from 'vue'

import { type TimelineChapter, chapterSegments, seekMsForRatio } from '@/utils/clipTeachingTimeline'

const props = defineProps<{
  chapters: TimelineChapter[]
  startMs: number
  endMs: number
  currentMs: number
}>()

const emit = defineEmits<{
  seek: [ms: number]
}>()

const segments = computed(() => chapterSegments(props.chapters, props.startMs, props.endMs))
const span = computed(() => Math.max(props.endMs - props.startMs, 1))
const playhead = computed(() => {
  const ratio = (props.currentMs - props.startMs) / span.value
  return Math.min(100, Math.max(0, ratio * 100))
})

function onSeek(event: MouseEvent): void {
  const bar = event.currentTarget
  if (!(bar instanceof HTMLElement)) return
  const rect = bar.getBoundingClientRect()
  if (rect.width <= 0) return
  emit('seek', seekMsForRatio((event.clientX - rect.left) / rect.width, props.startMs, props.endMs))
}

function isCurrent(startMs: number, endMs: number): boolean {
  return props.currentMs >= startMs && props.currentMs < endMs
}
</script>

<template>
  <button
    type="button"
    class="clip-rail"
    @click="onSeek"
  >
    <span
      v-for="segment in segments"
      :key="segment.id"
      class="clip-rail-segment"
      :class="{ 'is-current': isCurrent(segment.startMs, segment.endMs) }"
      :style="{ left: `${segment.leftPercent}%`, width: `${segment.widthPercent}%` }"
      :title="segment.title"
    />
    <span
      class="clip-rail-playhead"
      :style="{ left: `${playhead}%` }"
    />
  </button>
</template>

<style scoped>
.clip-rail {
  position: relative;
  display: block;
  width: 100%;
  height: 14px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(28, 25, 23, 0.45);
  overflow: hidden;
  cursor: pointer;
}

.clip-rail-segment {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.55);
}

.clip-rail-segment.is-current {
  background: #facc15;
}

.clip-rail-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  margin-left: -1px;
  background: #fff;
}
</style>
