<script setup lang="ts">
/**
 * Swiss-stone 配图 panel: ai-gen-shell hero, up to half the canvas.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { Image, Images } from '@lucide/vue'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import { useLanguage } from '@/composables'
import type { ExplainResearchImage } from '@/composables/mindMap/useMindMapNodeExplain'
import {
  RESEARCH_IMAGE_REVEAL_MS,
  RESEARCH_IMAGE_SCROLL_PX_PER_SEC,
  researchStripMaxScroll,
  resolveExplainResearchPanelBox,
  stepResearchStripScroll,
  type ExplainResearchSide,
} from '@/utils/mindMapExplainResearch'

const props = withDefaults(
  defineProps<{
    visible: boolean
    nodeLabel: string
    images: ExplainResearchImage[]
    side?: ExplainResearchSide
    loading: boolean
    canvasContainer?: HTMLElement | null
  }>(),
  {
    images: () => [],
    side: 'right',
    canvasContainer: null,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()

const title = computed(
  () => props.nodeLabel.trim() || t('canvas.mindMapNodeExplain.titleFallback')
)

const incomingImages = computed(() => props.images.filter((image) => image.url))
const revealedImages = ref<ExplainResearchImage[]>([])
const pendingImages = ref<ExplainResearchImage[]>([])
let revealTimer: number | null = null

const pullingImages = computed(
  () =>
    revealedImages.value.length === 0 &&
    (props.loading || pendingImages.value.length > 0 || incomingImages.value.length > 0)
)

const stillPulling = computed(
  () =>
    props.loading ||
    pendingImages.value.length > 0 ||
    revealedImages.value.length < incomingImages.value.length
)

const heroTitle = computed(() =>
  stillPulling.value ? t('canvas.mindMapNodeExplain.research.imagesLoading') : title.value
)

const heroLine = computed(() => (stillPulling.value ? title.value : ''))

const emptyCopy = computed(() =>
  pullingImages.value
    ? t('canvas.mindMapNodeExplain.research.imagesLoading')
    : t('canvas.mindMapNodeExplain.research.imagesEmpty')
)

const panelStyle = ref<Record<string, string> | undefined>()
const viewportEl = ref<HTMLElement | null>(null)
const trackEl = ref<HTMLElement | null>(null)
const scrollOffset = ref(0)
let canvasObserver: ResizeObserver | null = null
let scrollRaf = 0
let scrollClock = 0
let scrollDirection: 1 | -1 = 1
let userResumeTimer: number | null = null
const userPausedScroll = ref(false)

const trackStyle = computed(() => ({
  transform: `translate3d(${-scrollOffset.value}px, 0, 0)`,
}))

function measurePanel(): void {
  const canvas = props.canvasContainer
  if (!canvas) {
    panelStyle.value = undefined
    return
  }
  const box = resolveExplainResearchPanelBox(canvas.getBoundingClientRect(), props.side)
  panelStyle.value = {
    left: `${box.left}px`,
    top: `${box.top}px`,
    width: `${box.width}px`,
    height: `${box.height}px`,
    right: 'auto',
    bottom: 'auto',
  }
}

function bindCanvasObserver(): void {
  unbindCanvasObserver()
  const canvas = props.canvasContainer
  if (!canvas || !props.visible) return
  canvasObserver = new ResizeObserver(() => measurePanel())
  canvasObserver.observe(canvas)
  window.addEventListener('resize', measurePanel)
}

function unbindCanvasObserver(): void {
  canvasObserver?.disconnect()
  canvasObserver = null
  window.removeEventListener('resize', measurePanel)
}

function stopAutoScroll(): void {
  if (scrollRaf) window.cancelAnimationFrame(scrollRaf)
  scrollRaf = 0
  scrollClock = 0
}

function clampScrollOffset(next: number): number {
  const viewport = viewportEl.value
  const track = trackEl.value
  if (!viewport || !track) return 0
  const maxScroll = researchStripMaxScroll(track.scrollWidth, viewport.clientWidth)
  if (maxScroll <= 0) return 0
  return Math.min(maxScroll, Math.max(0, next))
}

function tickAutoScroll(now: number): void {
  const viewport = viewportEl.value
  const track = trackEl.value
  if (!viewport || !track || !props.visible || userPausedScroll.value) {
    scrollClock = now
    scrollRaf = window.requestAnimationFrame(tickAutoScroll)
    return
  }
  const maxScroll = researchStripMaxScroll(track.scrollWidth, viewport.clientWidth)
  const elapsed = scrollClock ? Math.min(0.05, (now - scrollClock) / 1000) : 0
  scrollClock = now
  if (maxScroll > 0 && elapsed > 0) {
    const stepped = stepResearchStripScroll(
      scrollOffset.value,
      maxScroll,
      RESEARCH_IMAGE_SCROLL_PX_PER_SEC * elapsed,
      scrollDirection
    )
    scrollDirection = stepped.direction
    scrollOffset.value = stepped.scrollLeft
  }
  scrollRaf = window.requestAnimationFrame(tickAutoScroll)
}

function startAutoScroll(): void {
  if (scrollRaf || !props.visible) return
  scrollRaf = window.requestAnimationFrame(tickAutoScroll)
}

function clearUserResumeTimer(): void {
  if (userResumeTimer == null) return
  window.clearTimeout(userResumeTimer)
  userResumeTimer = null
}

function pauseAutoScrollForUser(): void {
  userPausedScroll.value = true
  clearUserResumeTimer()
  userResumeTimer = window.setTimeout(() => {
    userResumeTimer = null
    userPausedScroll.value = false
  }, 4000)
}

function onViewportWheel(event: WheelEvent): void {
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  if (!delta) return
  pauseAutoScrollForUser()
  scrollOffset.value = clampScrollOffset(scrollOffset.value + delta)
}

function stopRevealTimer(): void {
  if (revealTimer == null) return
  window.clearTimeout(revealTimer)
  revealTimer = null
}

function resetRevealQueue(): void {
  stopRevealTimer()
  pendingImages.value = []
  revealedImages.value = []
}

function enqueueIncomingImages(): void {
  const seen = new Set([
    ...revealedImages.value.map((image) => image.url),
    ...pendingImages.value.map((image) => image.url),
  ])
  const extra: ExplainResearchImage[] = []
  incomingImages.value.forEach((image) => {
    if (seen.has(image.url)) return
    extra.push(image)
    seen.add(image.url)
  })
  if (extra.length) pendingImages.value = [...pendingImages.value, ...extra]
  pumpRevealQueue()
}

function pumpRevealQueue(): void {
  if (revealTimer != null || pendingImages.value.length === 0) return
  const [next, ...rest] = pendingImages.value
  if (!next) return
  pendingImages.value = rest
  revealedImages.value = [...revealedImages.value, next]
  void nextTick(startAutoScroll)
  if (rest.length === 0) return
  revealTimer = window.setTimeout(() => {
    revealTimer = null
    pumpRevealQueue()
  }, RESEARCH_IMAGE_REVEAL_MS)
}

function handleClose(): void {
  emit('close')
}

function hideBrokenImage(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLElement)) return
  const shot = target.closest('.ne-research__shot')
  if (shot instanceof HTMLElement) shot.hidden = true
}

watch(
  () => [props.visible, props.canvasContainer, props.side] as const,
  ([isOpen]) => {
    if (!isOpen) {
      unbindCanvasObserver()
      resetRevealQueue()
      stopAutoScroll()
      clearUserResumeTimer()
      userPausedScroll.value = false
      scrollDirection = 1
      scrollOffset.value = 0
      return
    }
    measurePanel()
    bindCanvasObserver()
    void nextTick(startAutoScroll)
  },
  { immediate: true }
)

watch(
  () => incomingImages.value.map((image) => image.url).join('\n'),
  (urls) => {
    if (!urls) {
      resetRevealQueue()
      return
    }
    enqueueIncomingImages()
  }
)

onUnmounted(() => {
  stopRevealTimer()
  clearUserResumeTimer()
  stopAutoScroll()
  unbindCanvasObserver()
})
</script>

<template>
  <Teleport to="body">
    <aside
      v-if="visible"
      class="ne-research ai-gen-shell"
      :class="`ne-research--${side}`"
      :style="panelStyle"
      role="complementary"
      :aria-label="t('canvas.mindMapNodeExplain.research.title')"
      :aria-busy="loading"
      @mousedown.stop
      @click.stop
    >
      <AiGenerateGlassHero
        compact
        :ribbon="t('canvas.mindMapNodeExplain.research.images')"
        :title="heroTitle"
        :line1="heroLine"
        :icon="Images"
        :badge="Image"
        @close="handleClose"
      />

      <section class="ne-research__images">
        <div
          v-if="revealedImages.length"
          ref="viewportEl"
          class="ne-research__viewport"
          @pointerdown="pauseAutoScrollForUser"
          @wheel.passive="onViewportWheel"
        >
          <div
            ref="trackEl"
            class="ne-research__track"
            :style="trackStyle"
          >
            <a
              v-for="image in revealedImages"
              :key="image.url"
              class="ne-research__shot"
              :href="image.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              <img
                :src="image.url"
                :alt="image.title || t('canvas.mindMapNodeExplain.research.images')"
                referrerpolicy="no-referrer"
                @load="startAutoScroll"
                @error="hideBrokenImage"
              />
            </a>
          </div>
        </div>
        <p
          v-else
          class="ne-research__empty"
          :class="{ 'ne-research__empty--live': pullingImages }"
        >
          <span
            v-if="pullingImages"
            class="ne-research__pulse"
            aria-hidden="true"
          />
          {{ emptyCopy }}
        </p>
      </section>
    </aside>
  </Teleport>
</template>

<style scoped>
.ne-research {
  position: fixed;
  top: 0.75rem;
  bottom: var(--mm-side-rail-bottom, 0.75rem);
  z-index: 5050;
  display: flex;
  flex-direction: column;
  width: 50%;
  overflow: hidden;
}

.ne-research--right {
  right: 0.75rem;
  left: auto;
}

.ne-research--left {
  left: 0.75rem;
  right: auto;
}

.ne-research :deep(.ai-glass-hero) {
  flex-shrink: 0;
}

.ne-research :deep(.ai-glass-hero__title) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ne-research__images {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  padding: 0.35rem 0.85rem 0.9rem;
}

.ne-research__viewport {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

.ne-research__track {
  display: grid;
  height: 100%;
  width: max-content;
  grid-auto-columns: 15rem;
  grid-auto-flow: column;
  grid-template-rows: 1fr 1fr;
  gap: 0.65rem;
  will-change: transform;
}

.ne-research__shot {
  display: block;
  min-height: 9rem;
  overflow: hidden;
  border: 1px solid rgb(255 255 255 / 0.72);
  border-radius: 16px;
  background: rgb(255 255 255 / 0.55);
  box-shadow: 0 10px 22px rgb(15 23 42 / 0.08);
  animation: ne-research-shot-in 0.4s ease both;
}

.ne-research__shot img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ne-research__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  margin: auto 0;
  font-size: 0.82rem;
  font-weight: 550;
  color: var(--ai-muted, #6b7280);
}

.ne-research__empty--live {
  color: var(--ai-ink, #1f2937);
}

.ne-research__pulse {
  display: inline-block;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background: var(--ai-accent, #6366f1);
  animation: ne-research-pulse 1s ease-in-out infinite;
}

@keyframes ne-research-pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }

  50% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes ne-research-shot-in {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.96);
  }

  to {
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 720px) {
  .ne-research--right,
  .ne-research--left {
    left: 0.75rem;
    right: 0.75rem;
    width: auto;
  }

  .ne-research__track {
    grid-auto-columns: 12rem;
  }
}
</style>
