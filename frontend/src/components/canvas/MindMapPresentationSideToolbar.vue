<script setup lang="ts">
/**
 * Mind map presentation — vertical tool rail with expandable tool panels.
 */
import { computed, ref } from 'vue'

import { Brush, Crosshair, Eraser, Hand, LogOut, MonitorPlay, MousePointer2, PenLine, Timer } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { resolvePresentationTeleportTarget } from '@/composables/presentation/presentationDiagramEdit'
import {
  PRESENTATION_LASER_SIZE_OPTIONS,
  PRESENTATION_LASER_SIZE_SCALE,
  type PresentationLaserSize,
  laserSizeFromScale,
} from '@/config/presentationLaser'
import {
  PRESENTATION_BOARD_COLORS_TOOLBAR,
  type PresentationBoardColorId,
  type PresentationBoardThickness,
} from '@/config/presentationPen'
import { PRESENTATION_HIGHLIGHTER_PALETTE_TOOLBAR } from '@/config/presentationHighlighter'
import {
  PRESENTATION_POINTER_SCALE_MAX,
  PRESENTATION_POINTER_SCALE_MIN,
} from '@/stores/presentationPointer'
import { PRESENTATION_Z } from '@/config/uiConfig'
import type { MindMapPresentationToolId } from '@/types/diagram'

const sideRailStyle = { zIndex: PRESENTATION_Z.SIDE_RAIL } as const

const props = defineProps<{
  activeTool: MindMapPresentationToolId
  colorId: PresentationBoardColorId
  thickness: PresentationBoardThickness
  laserScale: number
  highlighterScale: number
  highlighterColorIndex: number
  strokeEraserActive: boolean
  showSlidesTool?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectTool', tool: MindMapPresentationToolId): void
  (e: 'selectColor', id: PresentationBoardColorId): void
  (e: 'selectThickness', value: PresentationBoardThickness): void
  (e: 'selectLaserSize', value: PresentationLaserSize): void
  (e: 'selectHighlighterColor', index: number): void
  (e: 'selectHighlighterScale', value: number): void
  (e: 'toggleStrokeEraser'): void
  (e: 'exit'): void
}>()

const { t } = useLanguage()

const thicknessOptions: PresentationBoardThickness[] = ['thin', 'medium', 'thick']
const activeLaserSize = computed(() => laserSizeFromScale(props.laserScale))

const floatingTip = ref<{ text: string; x: number; y: number } | null>(null)

function showFloatingTipForElement(element: HTMLElement, text: string): void {
  if (!text) return
  const rect = element.getBoundingClientRect()
  floatingTip.value = {
    text,
    x: rect.left - 12,
    y: rect.top + rect.height / 2,
  }
}

function hideFloatingTip(): void {
  floatingTip.value = null
}

function onToolMouseEnter(event: MouseEvent): void {
  const el = (event.target as HTMLElement).closest('[data-tip]') as HTMLElement | null
  if (!el) return
  showFloatingTipForElement(el, el.dataset.tip ?? '')
}

function onToolMouseLeave(event: MouseEvent): void {
  const related = event.relatedTarget as HTMLElement | null
  if (related?.closest('[data-tip]')) return
  hideFloatingTip()
}

const teleportTarget = computed(() => resolvePresentationTeleportTarget())

function toolClass(tool: MindMapPresentationToolId): string {
  return props.activeTool === tool ? 'presentation-tool-btn is-active' : 'presentation-tool-btn'
}

function thicknessLabel(value: PresentationBoardThickness): string {
  if (value === 'thin') return t('canvas.mindMapPresentationToolbar.penThin')
  if (value === 'thick') return t('canvas.mindMapPresentationToolbar.penThick')
  return t('canvas.mindMapPresentationToolbar.penMedium')
}

function laserSizeLabel(value: PresentationLaserSize): string {
  if (value === 'small') return t('canvas.mindMapPresentationToolbar.laserSmall')
  if (value === 'large') return t('canvas.mindMapPresentationToolbar.laserLarge')
  return t('canvas.mindMapPresentationToolbar.laserMedium')
}

function onHighlighterScaleInput(event: Event): void {
  const raw = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  emit('selectHighlighterScale', raw)
}
</script>

<template>
  <div
    class="mind-map-presentation-toolbar pointer-events-auto fixed right-3 top-1/2 -translate-y-1/2"
    :style="sideRailStyle"
    role="toolbar"
    :aria-label="t('canvas.mindMapPresentationToolbar.ariaLabel')"
  >
    <div
      class="presentation-tool-capsule overflow-visible rounded-xl border border-gray-200/80 bg-white/90 p-0.5 shadow-lg backdrop-blur-md dark:border-gray-600/80 dark:bg-gray-800/90"
    >
      <div
        class="presentation-tool-inner grid w-10 shrink-0 grid-cols-1 justify-items-center gap-0.5 rounded-lg bg-gray-50 dark:bg-gray-700/50"
        @mouseover="onToolMouseEnter"
        @mouseout="onToolMouseLeave"
      >
        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="toolClass('pointer')"
            :data-tip="t('canvas.mindMapPresentationToolbar.pointer')"
            :title="t('canvas.mindMapPresentationToolbar.pointer')"
            @click="emit('selectTool', 'pointer')"
          >
            <MousePointer2 class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="toolClass('hand')"
            :data-tip="t('canvas.zoomControls.hand')"
            :title="t('canvas.zoomControls.hand')"
            @click="emit('selectTool', 'hand')"
          >
            <Hand class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="toolClass('laser')"
            :data-tip="t('canvas.presentationSideToolbar.laser')"
            :title="t('canvas.presentationSideToolbar.laser')"
            @click="emit('selectTool', 'laser')"
          >
            <Crosshair class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <template v-if="props.activeTool === 'laser'">
          <div
            class="toolbar-divider"
            aria-hidden="true"
          />
          <div
            class="tool-params-block w-full"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.laserSizeGroup')"
          >
            <div
              v-for="size in PRESENTATION_LASER_SIZE_OPTIONS"
              :key="size"
              class="presentation-tool-slot flex h-10 w-full items-center justify-center"
            >
              <button
                type="button"
                class="laser-size-btn"
                :class="{ 'is-selected': activeLaserSize === size }"
                :data-tip="laserSizeLabel(size)"
                :title="laserSizeLabel(size)"
                :aria-label="laserSizeLabel(size)"
                @click="emit('selectLaserSize', size)"
              >
                <span
                  class="laser-size-dot"
                  :class="`laser-size-dot--${size}`"
                />
              </button>
            </div>
          </div>
        </template>

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="toolClass('highlighter')"
            :data-tip="t('canvas.presentationSideToolbar.highlighter')"
            :title="t('canvas.presentationSideToolbar.highlighter')"
            @click="emit('selectTool', 'highlighter')"
          >
            <Brush class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <template v-if="props.activeTool === 'highlighter'">
          <div
            class="toolbar-divider"
            aria-hidden="true"
          />
          <div
            class="tool-params-block w-full"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.highlighterColorGroup')"
          >
            <div
              v-for="(color, index) in PRESENTATION_HIGHLIGHTER_PALETTE_TOOLBAR"
              :key="index"
              class="presentation-tool-slot flex h-10 w-full items-center justify-center"
            >
              <button
                type="button"
                class="pen-color-btn"
                :class="{ 'is-selected': props.highlighterColorIndex === index }"
                :data-tip="t('canvas.mindMapPresentationToolbar.highlighterColor')"
                @click="emit('selectHighlighterColor', index)"
              >
                <span
                  class="pen-color-btn__dot"
                  :style="{ backgroundColor: color.swatch }"
                />
              </button>
            </div>
          </div>

          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div
            class="highlighter-thickness-block w-full px-1.5 py-2"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.thicknessGroup')"
          >
            <input
              type="range"
              class="highlighter-thickness-slider"
              :min="PRESENTATION_POINTER_SCALE_MIN"
              :max="PRESENTATION_POINTER_SCALE_MAX"
              step="0.1"
              :value="props.highlighterScale"
              :aria-label="t('canvas.mindMapPresentationToolbar.highlighterThickness')"
              @input="onHighlighterScaleInput"
            />
          </div>

          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div class="tool-params-eraser flex h-10 w-full items-center justify-center">
            <button
              type="button"
              class="presentation-tool-btn"
              :class="{ 'is-active': props.strokeEraserActive }"
              :data-tip="t('canvas.mindMapPresentationToolbar.eraser')"
              :title="t('canvas.mindMapPresentationToolbar.eraser')"
              @click="emit('toggleStrokeEraser')"
            >
              <Eraser class="h-5 w-5 shrink-0" />
            </button>
          </div>
        </template>

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="[toolClass('pen'), 'presentation-tool-btn--pen']"
            :data-tip="t('canvas.mindMapPresentationToolbar.classroomBoard')"
            :title="t('canvas.mindMapPresentationToolbar.classroomBoard')"
            @click="emit('selectTool', 'pen')"
          >
            <PenLine class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <template v-if="props.activeTool === 'pen'">
          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div
            class="tool-params-block w-full"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.colorGroup')"
          >
            <div
              v-for="color in PRESENTATION_BOARD_COLORS_TOOLBAR"
              :key="color.id"
              class="presentation-tool-slot flex h-10 w-full items-center justify-center"
            >
              <button
                type="button"
                class="pen-color-btn"
                :class="{ 'is-selected': props.colorId === color.id }"
                :data-tip="t(color.labelKey)"
                :title="t(color.labelKey)"
                @click="emit('selectColor', color.id)"
              >
                <span
                  class="pen-color-btn__dot"
                  :style="{ backgroundColor: color.swatch }"
                />
              </button>
            </div>
          </div>

          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div
            class="tool-params-block w-full"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.thicknessGroup')"
          >
            <div
              v-for="option in thicknessOptions"
              :key="option"
              class="presentation-tool-slot flex h-10 w-full items-center justify-center"
            >
              <button
                type="button"
                class="pen-thickness-btn"
                :class="{ 'is-selected': props.thickness === option }"
                :data-tip="thicknessLabel(option)"
                :title="thicknessLabel(option)"
                :aria-label="thicknessLabel(option)"
                @click="emit('selectThickness', option)"
              >
                <span
                  class="pen-thickness-preview"
                  :class="`pen-thickness-preview--${option}`"
                />
              </button>
            </div>
          </div>

          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div class="tool-params-eraser flex h-10 w-full items-center justify-center">
            <button
              type="button"
              class="presentation-tool-btn"
              :class="{ 'is-active': props.strokeEraserActive }"
              :data-tip="t('canvas.mindMapPresentationToolbar.eraser')"
              :title="t('canvas.mindMapPresentationToolbar.eraser')"
              @click="emit('toggleStrokeEraser')"
            >
              <Eraser class="h-5 w-5 shrink-0" />
            </button>
          </div>
        </template>

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            :class="toolClass('timer')"
            :data-tip="t('canvas.presentationSideToolbar.timer')"
            :title="t('canvas.presentationSideToolbar.timer')"
            @click="emit('selectTool', 'timer')"
          >
            <Timer class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <div
          v-if="props.showSlidesTool !== false"
          class="presentation-tool-slot flex h-10 w-full items-center justify-center"
        >
          <button
            type="button"
            :class="toolClass('slides')"
            :data-tip="t('canvas.mindMapPresentationToolbar.slides')"
            :title="t('canvas.mindMapPresentationToolbar.slides')"
            @click="emit('selectTool', 'slides')"
          >
            <MonitorPlay class="h-5 w-5 shrink-0" />
          </button>
        </div>

        <div
          class="toolbar-divider"
          aria-hidden="true"
        />

        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <button
            type="button"
            class="presentation-tool-btn presentation-tool-btn--exit"
            :data-tip="t('canvas.mindMapPresentationToolbar.exit')"
            :title="t('canvas.mindMapPresentationToolbar.exit')"
            @click="emit('exit')"
          >
            <LogOut class="h-5 w-5 shrink-0" />
          </button>
        </div>
      </div>
    </div>

    <Teleport :to="teleportTarget">
      <div
        v-if="floatingTip"
        class="presentation-rail-floating-tip pointer-events-none fixed whitespace-nowrap"
        :style="{
          left: `${floatingTip.x}px`,
          top: `${floatingTip.y}px`,
          transform: 'translate(-100%, -50%)',
          zIndex: 100300,
        }"
      >
        {{ floatingTip.text }}
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.toolbar-divider {
  width: 100%;
  height: 1px;
  margin: 0.125rem 0;
  background: rgb(229 231 235);
}

.dark .toolbar-divider {
  background: rgb(75 85 99);
}

.tool-params-block,
.highlighter-thickness-block,
.tool-params-eraser {
  width: 100%;
  background: rgb(239 246 255);
  border-radius: 10px;
}

.dark .tool-params-block,
.dark .highlighter-thickness-block,
.dark .tool-params-eraser {
  background: rgb(30 58 95 / 0.55);
}

.presentation-rail-floating-tip {
  padding: 0.35rem 0.55rem;
  border-radius: 0.5rem;
  background: rgb(17 24 39 / 0.92);
  color: #fff;
  font-size: 0.75rem;
  line-height: 1.25;
  box-shadow: 0 4px 14px rgb(15 23 42 / 0.18);
}

.presentation-tool-btn,
.pen-color-btn,
.pen-thickness-btn,
.laser-size-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 40px;
  height: 40px;
  min-width: 40px;
  min-height: 40px;
  margin-inline: auto;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: #374151;
  cursor: pointer;
}

.pen-color-btn:hover,
.pen-thickness-btn:hover,
.laser-size-btn:hover {
  background: rgb(243 244 246);
}

.pen-color-btn__dot {
  display: block;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.08);
}

.pen-color-btn.is-selected {
  box-shadow: inset 0 0 0 1.5px rgb(37 99 235 / 0.35);
  background: rgb(219 234 254);
}

.pen-color-btn.is-selected .pen-color-btn__dot {
  box-shadow:
    0 0 0 2px rgb(255 255 255),
    0 0 0 3.5px rgb(37 99 235 / 0.85);
}

.laser-size-dot {
  display: block;
  border-radius: 999px;
  background: rgb(239 68 68);
  box-shadow: 0 0 0 2px rgb(254 226 226);
}

.laser-size-dot--small {
  width: 6px;
  height: 6px;
}

.laser-size-dot--medium {
  width: 9px;
  height: 9px;
}

.laser-size-dot--large {
  width: 13px;
  height: 13px;
}

.laser-size-btn.is-selected {
  background: rgb(254 226 226);
  box-shadow: inset 0 0 0 1.5px rgb(248 113 113 / 0.55);
}

.pen-thickness-btn.is-selected {
  background: rgb(219 234 254);
  box-shadow: inset 0 0 0 1.5px rgb(147 197 253 / 0.65);
}

.pen-thickness-preview {
  display: block;
  border-radius: 999px;
  background: rgb(55 65 81);
}

.pen-thickness-preview--thin {
  width: 14px;
  height: 2px;
}

.pen-thickness-preview--medium {
  width: 20px;
  height: 3.5px;
}

.pen-thickness-preview--thick {
  width: 26px;
  height: 6px;
}

.highlighter-thickness-slider {
  width: 100%;
  height: 4px;
  accent-color: rgb(37 99 235);
  cursor: pointer;
}

.presentation-tool-btn.is-active {
  background-color: #dbeafe;
  color: #2563eb;
}

.presentation-tool-btn--pen.is-active {
  background-color: rgb(220 252 231);
  color: rgb(22 163 74);
  box-shadow: inset 0 0 0 1px rgb(134 239 172 / 0.65);
}

.presentation-tool-btn--exit {
  color: rgb(220 38 38);
}

.presentation-tool-btn--exit:hover {
  background-color: rgb(254 226 226);
  color: rgb(185 28 28);
}

.presentation-tool-btn:hover {
  background-color: #f3f4f6;
}

.dark .presentation-tool-btn,
.dark .pen-color-btn,
.dark .pen-thickness-btn,
.dark .laser-size-btn {
  color: #e5e7eb;
}

.dark .presentation-tool-btn.is-active {
  background-color: #1e3a5f;
  color: #60a5fa;
}

.dark .presentation-tool-btn--pen.is-active {
  background-color: rgb(6 78 59 / 0.55);
  color: rgb(110 231 183);
}

.dark .presentation-tool-btn--exit {
  color: rgb(248 113 113);
}

.dark .presentation-tool-btn--exit:hover {
  background-color: rgb(127 29 29 / 0.45);
}

.dark .presentation-tool-btn:hover,
.dark .pen-color-btn:hover,
.dark .pen-thickness-btn:hover,
.dark .laser-size-btn:hover {
  background-color: #4b5563;
}

.dark .pen-thickness-preview {
  background: rgb(229 231 235);
}

.dark .pen-color-btn.is-selected {
  background: rgb(30 58 95);
  box-shadow: inset 0 0 0 1.5px rgb(96 165 250 / 0.4);
}

.dark .laser-size-btn.is-selected {
  background: rgb(127 29 29 / 0.45);
}
</style>
