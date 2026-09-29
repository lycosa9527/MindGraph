<script setup lang="ts">
/**
 * Bottom filmstrip of the diagrams chosen for this demo.
 */
import { nextTick, ref, watch } from 'vue'

import type { DemoDeckSlide } from '@/composables/demo/useLibraryDemo'

const props = defineProps<{
  slides: DemoDeckSlide[]
  activeIndex: number
}>()

const emit = defineEmits<{ select: [index: number] }>()

const scroller = ref<HTMLElement | null>(null)

watch(
  () => props.activeIndex,
  async () => {
    await nextTick()
    const root = scroller.value
    const active = root?.querySelector<HTMLElement>('[data-active="true"]')
    active?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
  }
)

function label(slide: DemoDeckSlide): string {
  const trimmed = slide.title.trim()
  return trimmed || ' '
}
</script>

<template>
  <div
    ref="scroller"
    class="demo-strip"
    role="tablist"
  >
    <button
      v-for="(slide, index) in slides"
      :key="slide.id"
      type="button"
      class="demo-strip__cell"
      role="tab"
      :data-active="index === activeIndex ? 'true' : 'false'"
      :aria-selected="index === activeIndex"
      @click="emit('select', index)"
    >
      <img
        v-if="slide.thumbnail"
        :src="slide.thumbnail"
        alt=""
        class="demo-strip__thumb"
      />
      <span
        v-else
        class="demo-strip__fallback"
        >{{ label(slide).slice(0, 1) }}</span
      >
      <span class="demo-strip__title">{{ label(slide) }}</span>
    </button>
  </div>
</template>

<style scoped>
.demo-strip {
  display: flex;
  gap: 0.65rem;
  overflow-x: auto;
  padding: 0.7rem 0.85rem;
  border: 1px solid rgb(255 255 255 / 0.46);
  border-radius: 1rem;
  background: rgb(250 250 249 / 0.28);
  backdrop-filter: blur(18px);
}

.demo-strip__cell {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 0.35rem;
  width: 7.5rem;
  padding: 0.35rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  background: transparent;
  color: #1c1917;
  cursor: pointer;
}

.demo-strip__cell[data-active='true'] {
  border-color: #1c1917;
  box-shadow: 0 0 0 1px #1c1917;
}

.demo-strip__thumb,
.demo-strip__fallback {
  width: 100%;
  height: 3.4rem;
  border-radius: 0.45rem;
  object-fit: cover;
  background: rgb(255 255 255 / 0.55);
}

.demo-strip__fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 600;
}

.demo-strip__title {
  overflow: hidden;
  font-size: 0.72rem;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}
</style>
