<script setup lang="ts">
/**
 * Full-bleed login films behind the library demo. Still stays underneath
 * until a clip can play; reduced motion and playback errors keep the still.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { demoHeroSrc } from '@/composables/demo/demoPlayback'
import { AUTH_LOGIN_HERO_STILL_SRC } from '@/utils/authLoginHero'

const props = defineProps<{ slideIndex: number }>()

const reduceMotion = ref(false)
const failed = ref(false)
const front = ref<0 | 1>(0)
const sources = ref<[string, string]>(['', ''])
const ready = ref<[boolean, boolean]>([false, false])

let motionMq: MediaQueryList | null = null

const showVideo = computed(() => !reduceMotion.value && !failed.value)

function onMotionChange(): void {
  reduceMotion.value = Boolean(motionMq?.matches)
}

onMounted(() => {
  motionMq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reduceMotion.value = motionMq.matches
  motionMq.addEventListener('change', onMotionChange)
  sources.value = [demoHeroSrc(props.slideIndex), '']
})

onBeforeUnmount(() => {
  motionMq?.removeEventListener('change', onMotionChange)
})

watch(
  () => props.slideIndex,
  (index) => {
    if (!showVideo.value) return
    const next = demoHeroSrc(index)
    if (sources.value[front.value] === next) return
    const incoming: 0 | 1 = front.value === 0 ? 1 : 0
    ready.value[incoming] = false
    sources.value[incoming] = next
  }
)

function onCanPlay(slot: 0 | 1): void {
  ready.value[slot] = true
  if (slot !== front.value && sources.value[slot]) {
    front.value = slot
  }
}

function onError(): void {
  failed.value = true
}

function slotClass(slot: 0 | 1): string {
  const visible = front.value === slot && ready.value[slot]
  return visible ? 'demo-film__video demo-film__video--on' : 'demo-film__video'
}
</script>

<template>
  <div
    class="demo-film"
    aria-hidden="true"
  >
    <img
      :src="AUTH_LOGIN_HERO_STILL_SRC"
      alt=""
      class="demo-film__still"
    />
    <template v-if="showVideo">
      <video
        v-if="sources[0]"
        :class="slotClass(0)"
        :src="sources[0]"
        autoplay
        muted
        loop
        playsinline
        preload="auto"
        @canplay="onCanPlay(0)"
        @error="onError"
      />
      <video
        v-if="sources[1]"
        :class="slotClass(1)"
        :src="sources[1]"
        autoplay
        muted
        loop
        playsinline
        preload="auto"
        @canplay="onCanPlay(1)"
        @error="onError"
      />
    </template>
    <div class="demo-film__wash" />
  </div>
</template>

<style scoped>
.demo-film {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: #1c1917;
}

.demo-film__still,
.demo-film__video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.demo-film__video {
  opacity: 0;
  transition: opacity 700ms ease;
}

.demo-film__video--on {
  opacity: 1;
}

.demo-film__wash {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse at center,
    rgb(250 250 249 / 0.55) 0%,
    rgb(250 250 249 / 0.28) 46%,
    rgb(28 25 23 / 0.38) 100%
  );
}

@media (prefers-reduced-motion: reduce) {
  .demo-film__video {
    transition: none;
  }
}
</style>
