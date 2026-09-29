<script setup lang="ts">
/**
 * Fullscreen library demo: gallery brand lockup, frosted diagram and caption,
 * and a thumbnail filmstrip over the login films.
 */
import { computed, onBeforeUnmount, watch } from 'vue'

import { ElAvatar } from 'element-plus'

import { Pause, Play } from '@lucide/vue'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import I18nText from '@/components/common/I18nText.vue'
import DemoCaptionHtml from '@/components/demo/DemoCaptionHtml.vue'
import DemoFilmBackdrop from '@/components/demo/DemoFilmBackdrop.vue'
import DemoSlideCanvas from '@/components/demo/DemoSlideCanvas.vue'
import DemoSlideStrip from '@/components/demo/DemoSlideStrip.vue'
import {
  demoCaptionHtml,
  demoFontColor,
  demoFontFamily,
} from '@/composables/demo/demoCaptionDefaults'
import { useLibraryDemo } from '@/composables/demo/useLibraryDemo'
import { getDiagramTypeDisplayName } from '@/composables/editor/useDiagramLabels'
import { useUIStore } from '@/stores/ui'

const {
  stageOpen,
  deck,
  slideIndex,
  paused,
  phase,
  closeStage,
  step,
  jumpTo,
  togglePause,
  advanceAfterTour,
} = useLibraryDemo()
const uiStore = useUIStore()

const slide = computed(() => deck.value[slideIndex.value] ?? null)

const typeName = computed(() => {
  const current = slide.value
  if (!current) return ''
  return getDiagramTypeDisplayName(current.diagramType, uiStore.language)
})

const captionStyle = computed(() => {
  const caption = slide.value?.caption
  if (!caption) return {}
  return {
    fontSize: `${caption.fontSize}px`,
    fontFamily: demoFontFamily(caption.fontFace),
    color: demoFontColor(caption.fontColor),
  }
})

function onKey(event: KeyboardEvent): void {
  if (!stageOpen.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    closeStage()
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    step(1)
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    step(-1)
    return
  }
  if (event.key === ' ') {
    event.preventDefault()
    togglePause()
  }
}

let lockedScroll = false
let previousOverflow = ''

function lockScroll(): void {
  if (lockedScroll || typeof document === 'undefined') return
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  lockedScroll = true
}

function unlockScroll(): void {
  if (!lockedScroll || typeof document === 'undefined') return
  document.body.style.overflow = previousOverflow
  lockedScroll = false
}

watch(
  stageOpen,
  (open) => {
    if (open) {
      window.addEventListener('keydown', onKey)
      lockScroll()
      return
    }
    window.removeEventListener('keydown', onKey)
    unlockScroll()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  unlockScroll()
  if (stageOpen.value) closeStage()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="stageOpen && slide"
      class="demo-stage"
      role="dialog"
      aria-modal="true"
    >
      <DemoFilmBackdrop :slide-index="slideIndex" />

      <button
        type="button"
        class="demo-stage__exit"
        @click="closeStage"
      >
        <I18nText k="sidebar.demo.exit" />
      </button>

      <div class="demo-stage__body">
        <header class="demo-stage__brand">
          <div class="demo-stage__logo-wrap">
            <div class="demo-stage__logo-inner">
              <ElAvatar
                :src="mindgraphLogo"
                alt="MindGraph"
                :size="80"
                shape="square"
                class="demo-stage__logo"
              />
            </div>
          </div>
          <div class="demo-stage__brand-text">
            <h1 class="demo-stage__title">MindGraph</h1>
            <p class="demo-stage__slogan">
              <I18nText k="landing.international.subtitle" />
            </p>
          </div>
        </header>

        <section class="demo-glass demo-stage__diagram">
          <DemoSlideCanvas
            :diagram-id="slide.id"
            :diagram-type="slide.diagramType"
            :phase="phase"
            :paused="paused"
            :thumbnail="slide.thumbnail"
            @tour-done="advanceAfterTour"
          />
          <button
            type="button"
            class="demo-stage__pause"
            @click="togglePause"
          >
            <Play
              v-if="paused"
              class="h-4 w-4"
            />
            <Pause
              v-else
              class="h-4 w-4"
            />
            <I18nText :k="paused ? 'sidebar.demo.play' : 'sidebar.demo.pause'" />
          </button>
          <aside class="demo-stage__caption">
            <p class="demo-stage__type">{{ typeName }}</p>
            <DemoCaptionHtml
              :key="slide.id"
              class="demo-stage__copy"
              :style="captionStyle"
              :html="demoCaptionHtml(slide.caption)"
            />
          </aside>
        </section>

        <footer class="demo-stage__foot">
          <DemoSlideStrip
            :slides="deck"
            :active-index="slideIndex"
            @select="jumpTo"
          />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.demo-stage {
  position: fixed;
  inset: 0;
  z-index: 5000;
  color: #1c1917;
}

.demo-stage__body {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  height: 100%;
  padding: 1.25rem 1.5rem 1rem;
  box-sizing: border-box;
}

.demo-stage__brand {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 1.15rem;
  padding-top: 0.15rem;
}

@property --demo-rainbow-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.demo-stage__logo-wrap {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  border-radius: 18px;
}

.demo-stage__logo-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 18px;
  padding: 4px;
  --demo-rainbow-angle: 0deg;
  background: conic-gradient(
    from var(--demo-rainbow-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 45deg,
    #a8a29e 90deg,
    #667eea 135deg,
    #764ba2 180deg,
    #667eea 225deg,
    #78716c 270deg,
    #d6d3d1 315deg,
    #e7e5e4 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: demo-rainbow 2.5s linear infinite;
}

@keyframes demo-rainbow {
  to {
    --demo-rainbow-angle: 360deg;
  }
}

.demo-stage__logo-inner {
  position: relative;
  width: 80px;
  height: 80px;
  overflow: hidden;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 4px 16px rgb(0 0 0 / 0.12);
}

.demo-stage__logo {
  border-radius: 14px;
}

.demo-stage__logo :deep(img) {
  object-fit: cover;
}

.demo-stage__brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.demo-stage__title {
  margin: 0 0 0.15rem;
  font-size: clamp(1.7rem, 3vw, 2.5rem);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  text-shadow: 0 1px 16px rgb(250 250 249 / 0.9);
}

.demo-stage__slogan {
  margin: 0;
  font-size: clamp(0.85rem, 1.4vw, 1rem);
  color: #44403c;
  text-shadow: 0 1px 12px rgb(250 250 249 / 0.92);
}

.demo-stage__diagram {
  position: relative;
  min-height: 0;
  margin: 1rem 0;
  overflow: hidden;
}

.demo-glass {
  min-height: 0;
  border: 1px solid rgb(255 255 255 / 0.48);
  border-radius: 1.25rem;
  background: rgb(250 250 249 / 0.22);
  backdrop-filter: blur(18px);
}

.demo-stage__caption {
  position: absolute;
  right: 0.85rem;
  bottom: 0.85rem;
  z-index: 4;
  display: flex;
  flex-direction: column;
  width: min(22rem, 34vw);
  max-height: 42%;
  padding: 0.9rem 1rem;
  overflow: auto;
  border: 1px solid rgb(255 255 255 / 0.55);
  border-radius: 1rem;
  background: rgb(250 250 249 / 0.78);
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
  backdrop-filter: blur(16px);
}

.demo-stage__type {
  margin: 0 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #44403c;
}

.demo-stage__copy {
  margin: 0;
  animation: demo-copy-in 480ms ease;
}

.demo-stage__foot {
  min-width: 0;
}

.demo-stage__exit,
.demo-stage__pause {
  border: 1px solid rgb(255 255 255 / 0.48);
  background: rgb(250 250 249 / 0.28);
  backdrop-filter: blur(18px);
  color: #1c1917;
  cursor: pointer;
  font-size: 0.8rem;
}

.demo-stage__exit {
  position: absolute;
  top: 1.1rem;
  left: 1.25rem;
  z-index: 2;
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
}

.demo-stage__pause {
  position: absolute;
  bottom: 0.85rem;
  left: 0.85rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  height: 2.4rem;
  padding: 0 0.85rem;
  border-radius: 999px;
}

@keyframes demo-copy-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .demo-stage__copy,
  .demo-stage__logo-wrap::before {
    animation: none;
  }
}
</style>
