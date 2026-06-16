<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { formatSidebarQuoteTextAuthor } from '@/types/sidebar-quotes'

const props = defineProps<{
  text: string
  author?: string
}>()

const MARQUEE_GAP_PX = 40
const MARQUEE_PX_PER_SEC = 24
const MARQUEE_PAUSE_MS = 1200

const viewportRef = ref<HTMLElement | null>(null)
const measureRef = ref<HTMLElement | null>(null)
const shouldScroll = ref(false)
const durationSec = ref(0)
const shiftPx = ref(0)

let resizeObserver: ResizeObserver | null = null

const displayLine = computed(() => formatSidebarQuoteTextAuthor(props.text, props.author))

const trackStyle = computed(() => {
  if (!shouldScroll.value) {
    return undefined
  }
  return {
    '--marquee-gap': `${MARQUEE_GAP_PX}px`,
    '--marquee-duration': `${durationSec.value}s`,
    '--marquee-pause': `${MARQUEE_PAUSE_MS}ms`,
    '--marquee-shift': `${shiftPx.value}px`,
  }
})

async function measureOverflow(): Promise<void> {
  await nextTick()
  const viewport = viewportRef.value
  const measure = measureRef.value
  if (!viewport || !measure || !displayLine.value) {
    shouldScroll.value = false
    return
  }

  const viewportWidth = viewport.clientWidth
  const textWidth = measure.scrollWidth
  const overflow = textWidth - viewportWidth

  if (overflow <= 2) {
    shouldScroll.value = false
    return
  }

  shouldScroll.value = true
  shiftPx.value = textWidth + MARQUEE_GAP_PX
  durationSec.value = Math.max(12, shiftPx.value / MARQUEE_PX_PER_SEC)
}

onMounted(() => {
  void measureOverflow()
  if (typeof ResizeObserver !== 'undefined' && viewportRef.value) {
    resizeObserver = new ResizeObserver(() => {
      void measureOverflow()
    })
    resizeObserver.observe(viewportRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

watch(
  () => [props.text, props.author] as const,
  () => {
    void measureOverflow()
  }
)
</script>

<template>
  <div
    v-if="displayLine"
    ref="viewportRef"
    class="sidebar-quote-marquee mt-0.5 min-w-0 max-w-full"
    :aria-label="displayLine"
    :title="displayLine"
  >
    <span
      ref="measureRef"
      class="sidebar-quote-marquee-measure"
      aria-hidden="true"
    >
      {{ displayLine }}
    </span>

    <div
      class="sidebar-quote-marquee-track"
      :class="{ 'sidebar-quote-marquee-track--scroll': shouldScroll }"
      :style="trackStyle"
    >
      <span
        class="sidebar-quote-marquee-text"
        aria-hidden="true"
      >
        {{ displayLine }}
      </span>
      <span
        v-if="shouldScroll"
        class="sidebar-quote-marquee-text sidebar-quote-marquee-text--clone"
        aria-hidden="true"
      >
        {{ displayLine }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.sidebar-quote-marquee {
  position: relative;
  overflow: hidden;
  height: 1.125rem;
  line-height: 1.125rem;
}

.sidebar-quote-marquee-measure {
  position: absolute;
  visibility: hidden;
  pointer-events: none;
  white-space: nowrap;
  font-size: 0.75rem;
  line-height: 1.125rem;
}

.sidebar-quote-marquee-track {
  display: inline-flex;
  align-items: center;
  min-width: 100%;
  white-space: nowrap;
}

.sidebar-quote-marquee-text {
  display: inline-block;
  font-size: 0.75rem;
  line-height: 1.125rem;
  color: #78716c;
  white-space: nowrap;
}

.sidebar-quote-marquee-text--clone {
  padding-left: var(--marquee-gap, 40px);
}

.sidebar-quote-marquee-track--scroll {
  width: max-content;
  animation: sidebar-quote-marquee-scroll var(--marquee-duration, 18s) linear infinite;
  animation-delay: var(--marquee-pause, 1200ms);
}

.sidebar-quote-marquee:hover .sidebar-quote-marquee-track--scroll {
  animation-play-state: paused;
}

@keyframes sidebar-quote-marquee-scroll {
  0% {
    transform: translateX(0);
  }

  100% {
    transform: translateX(calc(-1 * var(--marquee-shift, 0px)));
  }
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-quote-marquee-track--scroll {
    animation: none;
    max-width: 100%;
  }

  .sidebar-quote-marquee-text {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sidebar-quote-marquee-text--clone {
    display: none;
  }
}
</style>
