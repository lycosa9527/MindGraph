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
      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationSideToolbar.laser')"
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

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationSideToolbar.highlighter')"
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

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationSideToolbar.pen')"
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

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationSideToolbar.spotlight')"
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

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.presentationSideToolbar.timer')"
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

      <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
        <ElTooltip
          :content="t('canvas.toolbar.moreAppVirtualKeyboard')"
          placement="left"
        >
          <ElButton
            text
            size="small"
            :class="props.virtualKeyboardOpen ? 'presentation-tool-btn is-active' : 'presentation-tool-btn'"
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
.presentation-tool-btn.is-active {
  background-color: #dbeafe;
  color: #1d4ed8;
}
.dark .presentation-tool-btn.is-active {
  background-color: rgba(30, 64, 175, 0.45);
  color: #93c5fd;
}
</style>
