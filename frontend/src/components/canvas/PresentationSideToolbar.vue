<script setup lang="ts">
/**
 * Vertical presentation tools rail — right edge, laser through timer.
 */
import { ElButton, ElTooltip } from 'element-plus'

import {
  Brush,
  Keyboard,
  Maximize2,
  MousePointer2,
  PenLine,
  Square,
  Sun,
  Timer,
  Trash2,
} from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { PRESENTATION_Z } from '@/config/uiConfig'
import type { PresentationToolId } from '@/types/diagram'

const sideRailStyle = { zIndex: PRESENTATION_Z.SIDE_RAIL } as const

const props = defineProps<{
  activeTool: PresentationToolId
  virtualKeyboardOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectTool', tool: PresentationToolId): void
  (e: 'clearHighlighter'): void
  (e: 'fit'): void
  (e: 'exit'): void
  (e: 'toggleVirtualKeyboard'): void
}>()

const { t } = useLanguage()

function toolClass(tool: PresentationToolId): string {
  return props.activeTool === tool ? 'presentation-tool-btn is-active' : 'presentation-tool-btn'
}

function slotCurrentClass(tool: PresentationToolId): Record<string, boolean> {
  return { 'presentation-tool-slot--current': props.activeTool === tool }
}
</script>

<template>
  <div
    class="presentation-side-toolbar pointer-events-auto fixed right-3 top-1/2 flex w-fit -translate-y-1/2 flex-col rounded-xl border border-gray-200/80 bg-white/90 p-0.5 shadow-lg backdrop-blur-md dark:border-gray-600/80 dark:bg-gray-800/90"
    :style="sideRailStyle"
    role="toolbar"
    :aria-label="t('canvas.presentationSideToolbar.ariaLabel')"
  >
    <!-- Fixed w-10 column + per-row flex center: EP button/inner span otherwise reads wider than 40px and looks shifted -->
    <div
      class="presentation-side-toolbar-inner grid w-10 shrink-0 grid-cols-1 justify-items-center gap-0.5 rounded-lg bg-gray-50 dark:bg-gray-700/50"
    >
      <div
        class="presentation-tool-slot presentation-tool-slot--laser relative flex h-10 w-full items-center justify-center"
        :class="slotCurrentClass('laser')"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >1</span>
        <ElTooltip
          :content="`${t('canvas.presentationSideToolbar.laser')} (Ctrl+1)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="toolClass('laser')"
            @click="emit('selectTool', 'laser')"
          >
            <MousePointer2 class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="presentation-tool-slot presentation-tool-slot--highlighter relative flex h-10 w-full items-center justify-center"
        :class="slotCurrentClass('highlighter')"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >2</span>
        <ElTooltip
          :content="`${t('canvas.presentationSideToolbar.highlighter')} (Ctrl+2)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="toolClass('highlighter')"
            @click="emit('selectTool', 'highlighter')"
          >
            <Brush class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="presentation-tool-slot presentation-tool-slot--pen relative flex h-10 w-full items-center justify-center"
        :class="slotCurrentClass('pen')"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >3</span>
        <ElTooltip
          :content="`${t('canvas.presentationSideToolbar.pen')} (Ctrl+3)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="toolClass('pen')"
            @click="emit('selectTool', 'pen')"
          >
            <PenLine class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="presentation-tool-slot presentation-tool-slot--spotlight relative flex h-10 w-full items-center justify-center"
        :class="slotCurrentClass('spotlight')"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >4</span>
        <ElTooltip
          :content="`${t('canvas.presentationSideToolbar.spotlight')} (Ctrl+4)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="toolClass('spotlight')"
            @click="emit('selectTool', 'spotlight')"
          >
            <Sun class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="presentation-tool-slot presentation-tool-slot--timer relative flex h-10 w-full items-center justify-center"
        :class="slotCurrentClass('timer')"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >5</span>
        <ElTooltip
          :content="`${t('canvas.presentationSideToolbar.timer')} (Ctrl+5)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="toolClass('timer')"
            @click="emit('selectTool', 'timer')"
          >
            <Timer class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="presentation-tool-slot presentation-tool-slot--keyboard relative flex h-10 w-full items-center justify-center"
        :class="{ 'presentation-tool-slot--current': props.virtualKeyboardOpen }"
      >
        <span
          class="presentation-tool-index"
          aria-hidden="true"
        >6</span>
        <ElTooltip
          :content="`${t('canvas.toolbar.moreAppVirtualKeyboard')} (Ctrl+6)`"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="
              props.virtualKeyboardOpen
                ? 'presentation-tool-btn is-active'
                : 'presentation-tool-btn'
            "
            @click="emit('toggleVirtualKeyboard')"
          >
            <Keyboard class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div
        class="my-0.5 h-px w-full max-w-full bg-gray-200 dark:bg-gray-600"
        aria-hidden="true"
      />

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationContextMenu.clearHighlighter')"
          placement="left"
        >
          <ElButton
            text
            size="small"
            class="presentation-tool-btn"
            @click="emit('clearHighlighter')"
          >
            <Trash2 class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.zoomControls.fitCanvas')"
          placement="left"
        >
          <ElButton
            text
            size="small"
            class="presentation-tool-btn"
            @click="emit('fit')"
          >
            <Maximize2 class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.zoomControls.hidePresentationTools')"
          placement="left"
        >
          <ElButton
            text
            size="small"
            class="presentation-tool-btn text-red-600 dark:text-red-400"
            @click="emit('exit')"
          >
            <Square class="h-5 w-5 shrink-0" />
          </ElButton>
        </ElTooltip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.presentation-tool-slot {
  min-width: 0;
}

.presentation-tool-index {
  position: absolute;
  left: 2px;
  top: 2px;
  z-index: 1;
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.02em;
  pointer-events: none;
  user-select: none;
}

.presentation-tool-slot--current .presentation-tool-index {
  font-weight: 800;
}

/* Laser: warm index vs red icon */
.presentation-tool-slot--laser .presentation-tool-index {
  color: #ea580c;
}
.presentation-tool-slot--laser .presentation-tool-btn:not(.is-active) {
  color: #dc2626;
}
.presentation-tool-slot--laser .presentation-tool-btn.is-active {
  background-color: rgba(220, 38, 38, 0.14);
  color: #b91c1c;
}
.dark .presentation-tool-slot--laser .presentation-tool-index {
  color: #fdba74;
}
.dark .presentation-tool-slot--laser .presentation-tool-btn:not(.is-active) {
  color: #f87171;
}
.dark .presentation-tool-slot--laser .presentation-tool-btn.is-active {
  background-color: rgba(248, 113, 113, 0.22);
  color: #fecaca;
}

/* Highlighter: brown index vs yellow icon */
.presentation-tool-slot--highlighter .presentation-tool-index {
  color: #b45309;
}
.presentation-tool-slot--highlighter .presentation-tool-btn:not(.is-active) {
  color: #ca8a04;
}
.presentation-tool-slot--highlighter .presentation-tool-btn.is-active {
  background-color: rgba(202, 138, 4, 0.16);
  color: #a16207;
}
.dark .presentation-tool-slot--highlighter .presentation-tool-index {
  color: #fcd34d;
}
.dark .presentation-tool-slot--highlighter .presentation-tool-btn:not(.is-active) {
  color: #facc15;
}
.dark .presentation-tool-slot--highlighter .presentation-tool-btn.is-active {
  background-color: rgba(250, 204, 21, 0.18);
  color: #fef08a;
}

/* Pen: violet index vs indigo icon */
.presentation-tool-slot--pen .presentation-tool-index {
  color: #7c3aed;
}
.presentation-tool-slot--pen .presentation-tool-btn:not(.is-active) {
  color: #4f46e5;
}
.presentation-tool-slot--pen .presentation-tool-btn.is-active {
  background-color: rgba(79, 70, 229, 0.14);
  color: #4338ca;
}
.dark .presentation-tool-slot--pen .presentation-tool-index {
  color: #c4b5fd;
}
.dark .presentation-tool-slot--pen .presentation-tool-btn:not(.is-active) {
  color: #a5b4fc;
}
.dark .presentation-tool-slot--pen .presentation-tool-btn.is-active {
  background-color: rgba(165, 180, 252, 0.2);
  color: #e0e7ff;
}

/* Spotlight: deep amber index vs bright sun icon */
.presentation-tool-slot--spotlight .presentation-tool-index {
  color: #c2410c;
}
.presentation-tool-slot--spotlight .presentation-tool-btn:not(.is-active) {
  color: #ea580c;
}
.presentation-tool-slot--spotlight .presentation-tool-btn.is-active {
  background-color: rgba(234, 88, 12, 0.14);
  color: #c2410c;
}
.dark .presentation-tool-slot--spotlight .presentation-tool-index {
  color: #fb923c;
}
.dark .presentation-tool-slot--spotlight .presentation-tool-btn:not(.is-active) {
  color: #fdba74;
}
.dark .presentation-tool-slot--spotlight .presentation-tool-btn.is-active {
  background-color: rgba(251, 146, 60, 0.2);
  color: #ffedd5;
}

/* Timer: teal index vs cyan icon */
.presentation-tool-slot--timer .presentation-tool-index {
  color: #0f766e;
}
.presentation-tool-slot--timer .presentation-tool-btn:not(.is-active) {
  color: #0891b2;
}
.presentation-tool-slot--timer .presentation-tool-btn.is-active {
  background-color: rgba(8, 145, 178, 0.14);
  color: #0e7490;
}
.dark .presentation-tool-slot--timer .presentation-tool-index {
  color: #5eead4;
}
.dark .presentation-tool-slot--timer .presentation-tool-btn:not(.is-active) {
  color: #22d3ee;
}
.dark .presentation-tool-slot--timer .presentation-tool-btn.is-active {
  background-color: rgba(34, 211, 238, 0.18);
  color: #cffafe;
}

/* Keyboard: emerald index vs teal icon */
.presentation-tool-slot--keyboard .presentation-tool-index {
  color: #047857;
}
.presentation-tool-slot--keyboard .presentation-tool-btn:not(.is-active) {
  color: #0d9488;
}
.presentation-tool-slot--keyboard .presentation-tool-btn.is-active {
  background-color: rgba(13, 148, 136, 0.14);
  color: #0f766e;
}
.dark .presentation-tool-slot--keyboard .presentation-tool-index {
  color: #6ee7b7;
}
.dark .presentation-tool-slot--keyboard .presentation-tool-btn:not(.is-active) {
  color: #2dd4bf;
}
.dark .presentation-tool-slot--keyboard .presentation-tool-btn.is-active {
  background-color: rgba(45, 212, 191, 0.2);
  color: #ccfbf1;
}

.presentation-tool-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 40px;
  height: 40px;
  min-width: 40px;
  min-height: 40px;
  max-width: 40px;
  margin-inline: auto;
  padding: 0 !important;
  border-radius: 12px;
  color: #374151;
}

.presentation-tool-btn :deep(> span) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 0;
}

.presentation-tool-btn :deep(svg) {
  display: block;
}
.dark .presentation-tool-btn {
  color: #e5e7eb;
}
/* Align with CanvasToolbar / gray-100 hover on light */
.presentation-tool-btn:hover {
  background-color: #f3f4f6;
}
.dark .presentation-tool-btn:hover {
  background-color: #4b5563;
}
</style>
