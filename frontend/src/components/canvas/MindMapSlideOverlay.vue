<script setup lang="ts">
/**
 * Mind map slide show HUD — single-row compact dock with top handle toggle.
 */
import { computed, ref } from 'vue'

import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ChevronUp,
  LogOut,
  Pause,
  Play,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import { PRESENTATION_Z } from '@/config/uiConfig'
import type { MindMapSlideTraversalMode } from '@/utils/mindMapSlides'

const props = defineProps<{
  slideIndex: number
  slideCount: number
  slideTitle: string
  breadcrumb: string[]
  isOverviewSlide: boolean
  autoPlay: boolean
  autoPlayProgress: number
  transitioning: boolean
  canGoPrev: boolean
  canGoNext: boolean
  traversalMode: MindMapSlideTraversalMode
}>()

const emit = defineEmits<{
  (e: 'toggleAutoPlay'): void
  (e: 'prev'): void
  (e: 'next'): void
  (e: 'first'): void
  (e: 'last'): void
  (e: 'goTo', index: number): void
  (e: 'updateTraversalMode', mode: MindMapSlideTraversalMode): void
  (e: 'exit'): void
}>()

const { t } = useLanguage()

const collapsed = ref(false)

const regionLabel = computed(() => {
  const path =
    props.breadcrumb.length <= 1
      ? props.breadcrumb[0] ?? props.slideTitle
      : props.breadcrumb.join(' › ')
  return `${path} · ${props.slideIndex + 1} / ${props.slideCount}`
})

const collapseToggleLabel = computed(() =>
  collapsed.value
    ? t('canvas.mindMapSlideOverlay.expand')
    : t('canvas.mindMapSlideOverlay.collapse')
)

const progressPercent = computed(() => {
  if (props.slideCount <= 1) return 100
  return ((props.slideIndex + 1) / props.slideCount) * 100
})

const autoPlayFillWidth = computed(() => `${Math.round(props.autoPlayProgress * 100)}%`)

function onProgressClick(event: MouseEvent): void {
  if (props.slideCount <= 1 || props.transitioning) return
  const bar = event.currentTarget as HTMLElement
  const rect = bar.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  const index = Math.min(props.slideCount - 1, Math.floor(ratio * props.slideCount))
  emit('goTo', index)
}

function toggleCollapsed(): void {
  collapsed.value = !collapsed.value
}
</script>

<template>
  <div
    class="mind-map-slide-overlay pointer-events-auto fixed bottom-5 left-1/2 z-40 -translate-x-1/2 rounded-2xl border border-gray-200/75 bg-white/95 shadow-2xl shadow-slate-900/10 backdrop-blur-xl dark:border-gray-600/70 dark:bg-gray-900/92 dark:shadow-black/30"
    :class="{ 'is-collapsed': collapsed }"
    :style="{ zIndex: PRESENTATION_Z.TIMER_OVERLAY - 1 }"
    role="region"
    :aria-label="regionLabel"
  >
    <button
      type="button"
      class="dock-toggle"
      :aria-label="collapseToggleLabel"
      :title="collapseToggleLabel"
      @click="toggleCollapsed"
    >
      <ChevronUp
        v-if="collapsed"
        class="dock-toggle-icon"
      />
      <span
        v-else
        class="dock-toggle-grip"
        aria-hidden="true"
      />
    </button>

    <button
      type="button"
      class="slide-progress"
      :aria-label="t('canvas.mindMapSlideOverlay.progress')"
      :disabled="transitioning || slideCount <= 1"
      @click="onProgressClick"
    >
      <span
        class="slide-progress-fill"
        :style="{ width: `${progressPercent}%` }"
      />
      <span
        v-if="autoPlay"
        class="slide-progress-autoplay"
        :style="{ width: autoPlayFillWidth }"
      />
    </button>

    <Transition name="slide-toolbar-collapse">
      <div
        v-if="!collapsed"
        class="slide-toolbar"
      >
        <div
          class="traversal-mode"
          role="group"
          :aria-label="t('canvas.mindMapSlideOverlay.traversalMode')"
        >
          <button
            type="button"
            class="traversal-mode-btn"
            :class="{ 'is-active': traversalMode === 'firstLevel' }"
            :title="t('canvas.mindMapSlideOverlay.firstLevel')"
            @click="emit('updateTraversalMode', 'firstLevel')"
          >
            {{ t('canvas.mindMapSlideOverlay.firstLevel') }}
          </button>
          <button
            type="button"
            class="traversal-mode-btn"
            :class="{ 'is-active': traversalMode === 'deep' }"
            :title="t('canvas.mindMapSlideOverlay.deep')"
            @click="emit('updateTraversalMode', 'deep')"
          >
            {{ t('canvas.mindMapSlideOverlay.deep') }}
          </button>
        </div>

        <div class="nav-cluster">
          <button
            type="button"
            class="icon-btn"
            :disabled="!canGoPrev || transitioning"
            :aria-label="t('canvas.mindMapSlideOverlay.first')"
            @click="emit('first')"
          >
            <ChevronsLeft class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="icon-btn"
            :disabled="!canGoPrev || transitioning"
            :aria-label="t('canvas.mindMapSlideOverlay.prev')"
            @click="emit('prev')"
          >
            <ChevronLeft class="h-4 w-4" />
          </button>
          <span class="nav-counter">{{ slideIndex + 1 }} / {{ slideCount }}</span>
          <button
            type="button"
            class="icon-btn"
            :disabled="!canGoNext || transitioning"
            :aria-label="t('canvas.mindMapSlideOverlay.next')"
            @click="emit('next')"
          >
            <ChevronRight class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="icon-btn"
            :disabled="!canGoNext || transitioning"
            :aria-label="t('canvas.mindMapSlideOverlay.last')"
            @click="emit('last')"
          >
            <ChevronsRight class="h-4 w-4" />
          </button>
        </div>

        <div class="toolbar-actions">
          <button
            type="button"
            class="autoplay-btn"
            :class="{ 'is-active': autoPlay }"
            @click="emit('toggleAutoPlay')"
          >
            <Pause
              v-if="autoPlay"
              class="h-4 w-4 shrink-0"
            />
            <Play
              v-else
              class="h-4 w-4 shrink-0"
            />
            <span>{{
              autoPlay
                ? t('canvas.mindMapSlideOverlay.stopAutoPlay')
                : t('canvas.mindMapSlideOverlay.startAutoPlay')
            }}</span>
          </button>

          <button
            type="button"
            class="icon-btn icon-btn--exit"
            :aria-label="t('canvas.mindMapSlideOverlay.exit')"
            :title="t('canvas.mindMapSlideOverlay.exit')"
            @click="emit('exit')"
          >
            <LogOut class="h-4 w-4" />
          </button>
        </div>
      </div>
    </Transition>

    <div
      v-if="collapsed"
      class="slide-collapsed-meta"
    >
      <span class="collapsed-counter">{{ slideIndex + 1 }} / {{ slideCount }}</span>
    </div>
  </div>
</template>

<style scoped>
.mind-map-slide-overlay {
  width: min(94vw, 34rem);
  transition: width 0.22s ease;
}

.mind-map-slide-overlay.is-collapsed {
  width: min(88vw, 11rem);
}

.dock-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 1.35rem;
  padding: 0;
  border: none;
  border-bottom: 1px solid rgb(241 245 249);
  background: transparent;
  cursor: pointer;
  color: rgb(148 163 184);
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.dock-toggle:hover {
  background: rgb(248 250 252);
  color: rgb(100 116 139);
}

.dock-toggle-grip {
  display: block;
  width: 2rem;
  height: 0.2rem;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.85;
}

.dock-toggle-icon {
  width: 0.9rem;
  height: 0.9rem;
}

.slide-toolbar-collapse-enter-active,
.slide-toolbar-collapse-leave-active {
  overflow: hidden;
  transition:
    opacity 0.2s ease,
    max-height 0.22s ease;
}

.slide-toolbar-collapse-enter-from,
.slide-toolbar-collapse-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-toolbar-collapse-enter-to,
.slide-toolbar-collapse-leave-from {
  opacity: 1;
  max-height: 4rem;
}

.slide-collapsed-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.3rem 0.55rem 0.5rem;
}

.collapsed-counter {
  font-size: 0.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: rgb(51 65 85);
  user-select: none;
}

.slide-progress {
  position: relative;
  display: block;
  width: 100%;
  height: 0.2rem;
  padding: 0;
  border: none;
  background: rgb(226 232 240);
  cursor: pointer;
  overflow: hidden;
}

.slide-progress:disabled {
  cursor: default;
}

.slide-progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
  transition: width 0.35s ease;
  pointer-events: none;
}

.slide-progress-autoplay {
  position: absolute;
  inset: 0 auto 0 0;
  background: rgb(251 191 36 / 0.6);
  pointer-events: none;
  mix-blend-mode: multiply;
}

.slide-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  padding: 0.6rem 0.75rem;
}

.traversal-mode {
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  flex-shrink: 0;
  border-radius: 0.625rem;
  padding: 0.15rem;
  background: rgb(241 245 249);
}

.traversal-mode-btn {
  border: none;
  border-radius: 0.45rem;
  padding: 0.28rem 0.5rem;
  background: transparent;
  color: rgb(100 116 139);
  cursor: pointer;
  font-size: 0.6875rem;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
}

.traversal-mode-btn.is-active {
  background: #fff;
  color: rgb(30 41 59);
  box-shadow: 0 1px 2px rgb(15 23 42 / 0.07);
}

.nav-cluster {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  border-radius: 0.85rem;
  padding: 0.2rem 0.35rem;
  background: rgb(248 250 252);
  box-shadow: inset 0 0 0 1px rgb(226 232 240);
}

.nav-counter {
  min-width: 3.25rem;
  padding: 0 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: rgb(51 65 85);
  text-align: center;
  user-select: none;
}

.toolbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 0.55rem;
  background: transparent;
  color: rgb(51 65 85);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.icon-btn:hover:not(:disabled) {
  background: rgb(226 232 240);
}

.icon-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.icon-btn--exit {
  color: rgb(185 28 28);
}

.icon-btn--exit:hover {
  background: rgb(254 226 226);
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
  transition: background 0.15s ease;
  white-space: nowrap;
}

.autoplay-btn.is-active {
  background: rgb(255 237 213);
}

.dark .dock-toggle {
  border-bottom-color: rgb(51 65 85);
  color: rgb(100 116 139);
}

.dark .dock-toggle:hover {
  background: rgb(30 41 59);
  color: rgb(203 213 225);
}

.dark .slide-progress {
  background: rgb(51 65 85);
}

.dark .traversal-mode {
  background: rgb(51 65 85);
}

.dark .traversal-mode-btn {
  color: rgb(148 163 184);
}

.dark .traversal-mode-btn.is-active {
  background: rgb(30 41 59);
  color: rgb(241 245 249);
}

.dark .nav-cluster {
  background: rgb(30 41 59);
  box-shadow: inset 0 0 0 1px rgb(51 65 85);
}

.dark .nav-counter,
.dark .collapsed-counter {
  color: rgb(226 232 240);
}

.dark .icon-btn {
  color: rgb(226 232 240);
}

.dark .icon-btn:hover:not(:disabled) {
  background: rgb(71 85 105);
}

.dark .icon-btn--exit {
  color: rgb(252 165 165);
}

.dark .icon-btn--exit:hover {
  background: rgb(127 29 29 / 0.45);
}

@media (max-width: 640px) {
  .slide-toolbar {
    flex-wrap: wrap;
    justify-content: center;
    row-gap: 0.45rem;
  }

  .nav-cluster {
    order: -1;
    width: 100%;
    justify-content: center;
  }
}
</style>
