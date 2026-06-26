<script setup lang="ts">
/**
 * Mind map presentation — single vertical capsule; pen params expand downward in-column.
 */
import { Hand, MonitorPlay, MousePointer2, PenLine, Sun, Timer } from '@lucide/vue'

import { ElButton, ElTooltip } from 'element-plus'

import { useLanguage } from '@/composables'
import {
  PRESENTATION_BOARD_COLORS,
  type PresentationBoardColorId,
  type PresentationBoardThickness,
} from '@/config/presentationPen'
import { PRESENTATION_Z } from '@/config/uiConfig'
import type { MindMapPresentationToolId } from '@/types/diagram'

const sideRailStyle = { zIndex: PRESENTATION_Z.SIDE_RAIL } as const

const props = defineProps<{
  activeTool: MindMapPresentationToolId
  colorId: PresentationBoardColorId
  thickness: PresentationBoardThickness
  showSlidesTool?: boolean
}>()

const emit = defineEmits<{
  (e: 'selectTool', tool: MindMapPresentationToolId): void
  (e: 'selectColor', id: PresentationBoardColorId): void
  (e: 'selectThickness', value: PresentationBoardThickness): void
}>()

const { t } = useLanguage()

const thicknessOptions: PresentationBoardThickness[] = ['thin', 'medium', 'thick']

function toolClass(tool: MindMapPresentationToolId): string {
  return props.activeTool === tool ? 'presentation-tool-btn is-active' : 'presentation-tool-btn'
}

function thicknessLabel(value: PresentationBoardThickness): string {
  if (value === 'thin') return t('canvas.mindMapPresentationToolbar.penThin')
  if (value === 'thick') return t('canvas.mindMapPresentationToolbar.penThick')
  return t('canvas.mindMapPresentationToolbar.penMedium')
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
      class="presentation-tool-capsule overflow-hidden rounded-xl border border-gray-200/80 bg-white/90 p-0.5 shadow-lg backdrop-blur-md dark:border-gray-600/80 dark:bg-gray-800/90"
    >
      <div
        class="presentation-tool-inner grid w-10 shrink-0 grid-cols-1 justify-items-center gap-0.5 rounded-lg bg-gray-50 dark:bg-gray-700/50"
      >
        <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
          <ElTooltip
            :content="t('canvas.zoomControls.hand')"
            placement="left"
          >
            <ElButton
              text
              size="small"
              :class="toolClass('hand')"
              @click="emit('selectTool', 'hand')"
            >
              <Hand class="h-5 w-5 shrink-0" />
            </ElButton>
          </ElTooltip>
        </div>

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
            :content="t('canvas.mindMapPresentationToolbar.classroomBoard')"
            placement="left"
          >
            <ElButton
              text
              size="small"
              :class="[toolClass('pen'), 'presentation-tool-btn--pen']"
              @click="emit('selectTool', 'pen')"
            >
              <PenLine class="h-5 w-5 shrink-0" />
            </ElButton>
          </ElTooltip>
        </div>

        <template v-if="props.activeTool === 'pen'">
          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div
            class="pen-params-block w-full"
            role="group"
            :aria-label="t('canvas.mindMapPresentationToolbar.colorGroup')"
          >
            <div
              v-for="color in PRESENTATION_BOARD_COLORS"
              :key="color.id"
              class="presentation-tool-slot flex h-10 w-full items-center justify-center"
            >
              <ElTooltip
                :content="t(color.labelKey)"
                placement="left"
              >
                <button
                  type="button"
                  class="pen-color-btn"
                  :class="{ 'is-selected': props.colorId === color.id }"
                  @click="emit('selectColor', color.id)"
                >
                  <span
                    class="pen-color-btn__dot"
                    :style="{ backgroundColor: color.swatch }"
                  />
                </button>
              </ElTooltip>
            </div>
          </div>

          <div
            class="toolbar-divider"
            aria-hidden="true"
          />

          <div
            class="pen-params-block w-full"
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
                @click="emit('selectThickness', option)"
              >
                {{ thicknessLabel(option) }}
              </button>
            </div>
          </div>
        </template>

        <template v-if="props.showSlidesTool !== false">
          <div class="presentation-tool-slot flex h-10 w-full items-center justify-center">
            <ElTooltip
              :content="t('canvas.presentationSideToolbar.spotlight')"
              placement="left"
            >
              <ElButton
                text
                size="small"
                :class="[toolClass('spotlight'), 'presentation-tool-btn--spotlight']"
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
                :class="[toolClass('timer'), 'presentation-tool-btn--timer']"
                @click="emit('selectTool', 'timer')"
              >
                <Timer class="h-5 w-5 shrink-0" />
              </ElButton>
            </ElTooltip>
          </div>
        </template>

        <div
          v-if="props.showSlidesTool !== false"
          class="presentation-tool-slot flex h-10 w-full items-center justify-center"
        >
          <ElTooltip
            :content="t('canvas.mindMapPresentationToolbar.slides')"
            placement="left"
          >
            <ElButton
              text
              size="small"
              :class="toolClass('slides')"
              @click="emit('selectTool', 'slides')"
            >
              <MonitorPlay class="h-5 w-5 shrink-0" />
            </ElButton>
          </ElTooltip>
        </div>
      </div>
    </div>
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

.pen-color-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
}

.pen-color-btn:hover {
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

.dark .pen-color-btn:hover {
  background: rgb(75 85 99);
}

.dark .pen-color-btn.is-selected {
  background: rgb(30 58 95);
  box-shadow: inset 0 0 0 1.5px rgb(96 165 250 / 0.4);
}

.dark .pen-color-btn.is-selected .pen-color-btn__dot {
  box-shadow:
    0 0 0 2px rgb(30 41 59),
    0 0 0 3.5px rgb(96 165 250 / 0.9);
}

.pen-thickness-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: rgb(107 114 128);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
}

.pen-thickness-btn:hover {
  background: rgb(243 244 246);
  color: rgb(55 65 81);
}

.pen-thickness-btn.is-selected {
  background: rgb(219 234 254);
  color: rgb(37 99 235);
  box-shadow: inset 0 0 0 1.5px rgb(147 197 253 / 0.65);
}

.dark .pen-thickness-btn {
  color: rgb(156 163 175);
}

.dark .pen-thickness-btn:hover {
  background: rgb(75 85 99);
  color: rgb(229 231 235);
}

.dark .pen-thickness-btn.is-selected {
  background: rgb(30 58 95);
  color: rgb(96 165 250);
  box-shadow: inset 0 0 0 1.5px rgb(59 130 246 / 0.45);
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

.presentation-tool-btn.is-active {
  background-color: #dbeafe;
  color: #2563eb;
}

.presentation-tool-btn--pen.is-active {
  background-color: rgb(220 252 231);
  color: rgb(22 163 74);
  box-shadow: inset 0 0 0 1px rgb(134 239 172 / 0.65);
}

.presentation-tool-btn--spotlight.is-active {
  background-color: rgb(254 243 199);
  color: rgb(217 119 6);
  box-shadow: inset 0 0 0 1px rgb(252 211 77 / 0.65);
}

.presentation-tool-btn--timer.is-active {
  background-color: rgb(219 234 254);
  color: rgb(37 99 235);
  box-shadow: inset 0 0 0 1px rgb(147 197 253 / 0.65);
}

.presentation-tool-btn:hover {
  background-color: #f3f4f6;
}

.dark .presentation-tool-btn {
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

.dark .presentation-tool-btn--spotlight.is-active {
  background-color: rgb(120 53 15 / 0.45);
  color: rgb(252 211 77);
}

.dark .presentation-tool-btn--timer.is-active {
  background-color: rgb(30 58 95);
  color: rgb(96 165 250);
}

.dark .presentation-tool-btn:hover {
  background-color: #4b5563;
}
</style>
