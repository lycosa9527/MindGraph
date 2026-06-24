<script setup lang="ts">
/**
 * Collapsible mind-map side toolbar — blue handle sits outside the card.
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { ElTooltip } from 'element-plus'

import {
  ChevronLeft,
  ChevronRight,
  FileText,
  LayoutGrid,
  ListTree,
  Package,
  Sparkles,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  type MindMapSideToolId,
  useMindMapSideToolbarState,
} from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useLearningSheetCustomMode } from '@/composables/mindMap/useLearningSheetCustomMode'

const { t } = useLanguage()
const route = useRoute()
const { activeTool, handleToolSelect, openTool, sidebarExpanded } = useMindMapSideToolbarState()
const { isPickActive, isLearningSheetActive } = useLearningSheetCustomMode()

// Deep link from extension / Knowledge Space: open File Center on load.
onMounted(() => {
  if (route.query.openFileCenter === '1' && activeTool.value === null) {
    openTool('document_summary')
  }
})

const isExpanded = computed(() => sidebarExpanded.value)

const tools = computed(
  (): Array<{
    id: MindMapSideToolId
    labelKey: string
    icon: typeof ListTree
    accent: string
    active?: boolean
  }> => [
    {
      id: 'outline',
      labelKey: 'canvas.mindMapSideToolbar.outline',
      icon: ListTree,
      accent: 'sky',
      active: activeTool.value === 'outline',
    },
    {
      id: 'waterfall',
      labelKey: 'canvas.mindMapSideToolbar.waterfall',
      icon: LayoutGrid,
      accent: 'violet',
      active: activeTool.value === 'waterfall',
    },
    {
      id: 'learning_sheet',
      labelKey: 'canvas.mindMapSideToolbar.learningSheet',
      icon: Package,
      accent: 'amber',
      active:
        activeTool.value === 'learning_sheet' || isPickActive.value || isLearningSheetActive.value,
    },
    {
      id: 'one_sentence',
      labelKey: 'canvas.mindMapSideToolbar.oneSentence',
      icon: Sparkles,
      accent: 'emerald',
      active: activeTool.value === 'one_sentence',
    },
    {
      id: 'document_summary',
      labelKey: 'canvas.mindMapSideToolbar.documentSummary',
      icon: FileText,
      accent: 'rose',
      active: activeTool.value === 'document_summary',
    },
  ]
)

const toggleLabel = computed(() =>
  isExpanded.value ? t('canvas.mindMapSideToolbar.collapse') : t('canvas.mindMapSideToolbar.expand')
)

function onToggleClick(): void {
  sidebarExpanded.value = !sidebarExpanded.value
}

function onToolClick(toolId: MindMapSideToolId): void {
  handleToolSelect(toolId)
}
</script>

<template>
  <div
    class="mind-map-side-toolbar pointer-events-auto absolute left-3 top-1/2 z-30 flex -translate-y-1/2 items-stretch select-none"
  >
    <!-- Card -->
    <div
      class="mind-map-side-toolbar__card overflow-hidden transition-[width,opacity,transform] duration-200 ease-out"
      :class="isExpanded ? 'is-expanded' : 'is-collapsed'"
    >
      <nav
        class="mind-map-side-toolbar__inner"
        role="toolbar"
        :aria-label="t('canvas.mindMapSideToolbar.ariaLabel')"
        :aria-hidden="!isExpanded"
      >
        <ElTooltip
          v-for="tool in tools"
          :key="tool.id"
          :content="t(tool.labelKey)"
          placement="right"
          :show-after="280"
          :disabled="!isExpanded"
        >
          <button
            type="button"
            class="mind-map-side-toolbar__item"
            :class="[tool.active ? 'is-active' : '', `mind-map-side-toolbar__item--${tool.accent}`]"
            :aria-pressed="tool.active ? 'true' : 'false'"
            :tabindex="isExpanded ? 0 : -1"
            @click="onToolClick(tool.id)"
          >
            <span class="mind-map-side-toolbar__icon">
              <component
                :is="tool.icon"
                class="h-[17px] w-[17px]"
                :stroke-width="1.85"
              />
            </span>
            <span class="mind-map-side-toolbar__label">{{ t(tool.labelKey) }}</span>
          </button>
        </ElTooltip>
      </nav>
    </div>

    <!-- Blue handle — outside card, on the right edge -->
    <ElTooltip
      :content="toggleLabel"
      placement="right"
      :show-after="120"
    >
      <button
        type="button"
        class="mind-map-side-toolbar__handle"
        :class="{ 'is-collapsed': !isExpanded }"
        :aria-expanded="isExpanded"
        :aria-label="toggleLabel"
        @click="onToggleClick"
      >
        <ChevronRight
          v-if="!isExpanded"
          class="h-3.5 w-3.5"
          :stroke-width="2.75"
        />
        <ChevronLeft
          v-else
          class="h-3.5 w-3.5"
          :stroke-width="2.75"
        />
      </button>
    </ElTooltip>
  </div>
</template>

<style scoped>
.mind-map-side-toolbar__card {
  border: 1px solid rgb(226 232 240 / 0.95);
  border-right: none;
  border-radius: 1rem 0 0 1rem;
  background: rgb(255 255 255 / 0.97);
  box-shadow:
    -4px 0 16px -4px rgb(15 23 42 / 0.06),
    0 8px 24px -8px rgb(15 23 42 / 0.1);
  backdrop-filter: blur(14px);
}

.mind-map-side-toolbar__card.is-expanded {
  width: 5.75rem;
  opacity: 1;
}

.mind-map-side-toolbar__card.is-collapsed {
  width: 0;
  opacity: 0;
  pointer-events: none;
  border-color: transparent;
}

.mind-map-side-toolbar__inner {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  width: 5.75rem;
  padding: 0.5rem 0.375rem;
}

.mind-map-side-toolbar__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
  min-height: 3.35rem;
  padding: 0.45rem 0.2rem 0.4rem;
  border: none;
  border-radius: 0.625rem;
  background: transparent;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    transform 0.15s ease;
}

.mind-map-side-toolbar__item:hover {
  background: rgb(248 250 252);
  transform: translateY(-1px);
}

.mind-map-side-toolbar__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.55rem;
  color: rgb(71 85 105);
  background: rgb(248 250 252);
  box-shadow: inset 0 0 0 1px rgb(226 232 240 / 0.9);
  transition: all 0.15s ease;
}

.mind-map-side-toolbar__label {
  max-width: 4.8rem;
  text-align: center;
  font-size: 0.6875rem;
  line-height: 1.25;
  font-weight: 500;
  color: rgb(71 85 105);
}

.mind-map-side-toolbar__item.is-active .mind-map-side-toolbar__label {
  color: rgb(29 78 216);
  font-weight: 600;
}

.mind-map-side-toolbar__item--sky.is-active .mind-map-side-toolbar__icon,
.mind-map-side-toolbar__item--sky:hover .mind-map-side-toolbar__icon {
  color: rgb(2 132 199);
  background: rgb(224 242 254);
}

.mind-map-side-toolbar__item--violet:hover .mind-map-side-toolbar__icon,
.mind-map-side-toolbar__item--violet.is-active .mind-map-side-toolbar__icon {
  color: rgb(124 58 237);
  background: rgb(237 233 254);
}

.mind-map-side-toolbar__item--amber.is-active .mind-map-side-toolbar__icon,
.mind-map-side-toolbar__item--amber:hover .mind-map-side-toolbar__icon {
  color: rgb(217 119 6);
  background: rgb(254 243 199);
}

.mind-map-side-toolbar__item--emerald:hover .mind-map-side-toolbar__icon,
.mind-map-side-toolbar__item--emerald.is-active .mind-map-side-toolbar__icon {
  color: rgb(5 150 105);
  background: rgb(209 250 229);
}

.mind-map-side-toolbar__item--rose:hover .mind-map-side-toolbar__icon,
.mind-map-side-toolbar__item--rose.is-active .mind-map-side-toolbar__icon {
  color: rgb(225 29 72);
  background: rgb(255 228 230);
}

.mind-map-side-toolbar__handle {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  align-self: center;
  width: 1.125rem;
  padding: 1.45rem 0;
  border: none;
  border-radius: 0 9999px 9999px 0;
  color: rgb(255 255 255);
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  box-shadow:
    2px 0 10px -2px rgb(37 99 235 / 0.45),
    inset 1px 0 0 rgb(255 255 255 / 0.2);
  cursor: pointer;
  transition:
    background 0.18s ease,
    box-shadow 0.18s ease,
    padding 0.2s ease;
}

.mind-map-side-toolbar__handle:hover {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
  box-shadow:
    2px 0 14px -2px rgb(37 99 235 / 0.55),
    0 0 0 3px rgb(59 130 246 / 0.2);
}

.mind-map-side-toolbar__handle.is-collapsed {
  padding: 1.65rem 0;
  border-radius: 9999px;
}

.mind-map-side-toolbar__handle:focus-visible {
  outline: 2px solid rgb(96 165 250);
  outline-offset: 2px;
}

:global(.dark) .mind-map-side-toolbar__card {
  border-color: rgb(51 65 85 / 0.85);
  background: rgb(15 23 42 / 0.96);
}

:global(.dark) .mind-map-side-toolbar__icon {
  color: rgb(203 213 225);
  background: rgb(30 41 59);
  box-shadow: inset 0 0 0 1px rgb(51 65 85);
}

:global(.dark) .mind-map-side-toolbar__label {
  color: rgb(203 213 225);
}

:global(.dark) .mind-map-side-toolbar__item:hover {
  background: rgb(51 65 85 / 0.45);
}
</style>
