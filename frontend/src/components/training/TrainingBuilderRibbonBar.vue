<script setup lang="ts">
import { computed } from 'vue'

import { ElButton } from 'element-plus'

import {
  Clapperboard,
  Info,
  ListOrdered,
  PanelLeftClose,
  PanelLeftOpen,
  PenLine,
  Play,
  Presentation,
  Puzzle,
  Square,
} from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  BUILDER_CANVAS_TABS_TARGET,
  builderCanvasRibbonHosted,
  builderRibbonToolOwner,
} from '@/composables/training/builderCanvasRibbon'
import { useUIStore } from '@/stores/ui'

const props = defineProps<{
  tabs: readonly { id: string; labelKey: string }[]
  active: string
  previewing?: boolean
  readonly?: boolean
  saveLabel?: string
  saveTone?: 'saving' | 'dirty' | 'saved' | 'error'
}>()

const emit = defineEmits<{
  select: [id: string]
  save: []
  info: []
  preview: []
}>()

const TAB_ICONS = {
  slide: Presentation,
  marks: PenLine,
  media: Clapperboard,
  steps: ListOrdered,
  interact: Puzzle,
} as const

const { t } = useLanguage()
const uiStore = useUIStore()
const sidebarCollapsed = computed(() => uiStore.sidebarCollapsed)
const sidebarToggleLabel = computed(() =>
  sidebarCollapsed.value ? t('sidebar.expandSidebar') : t('sidebar.collapseSidebar')
)
const saveTitle = computed(() => {
  if (!props.saveLabel) return undefined
  return `${props.saveLabel} — ${t('canvas.topBar.autoSaveTitleSave')}`
})
const canvasHosted = builderCanvasRibbonHosted
const courseTabsActive = computed(
  () => !canvasHosted.value || builderRibbonToolOwner.value === 'course'
)

function tabIcon(id: string): (typeof TAB_ICONS)[keyof typeof TAB_ICONS] {
  if (id === 'slide' || id === 'marks' || id === 'media' || id === 'steps' || id === 'interact') {
    return TAB_ICONS[id]
  }
  return Presentation
}

function onTabKey(event: KeyboardEvent): void {
  if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
  event.preventDefault()
  const current = props.tabs.findIndex((tab) => tab.id === props.active)
  const delta = event.key === 'ArrowRight' ? 1 : -1
  const next = props.tabs[(current + delta + props.tabs.length) % props.tabs.length]
  if (!next) return
  emit('select', next.id)
  const host = event.currentTarget
  if (!(host instanceof HTMLElement)) return
  const buttons = host.querySelectorAll<HTMLButtonElement>('[role="tab"]')
  buttons[(current + delta + props.tabs.length) % props.tabs.length]?.focus()
}
</script>

<template>
  <div class="ribbon-bar">
    <div class="ribbon-bar__lead">
      <button
        type="button"
        class="ribbon-bar__sidebar"
        :title="sidebarToggleLabel"
        :aria-label="sidebarToggleLabel"
        @click="uiStore.toggleSidebar()"
      >
        <PanelLeftOpen
          v-if="sidebarCollapsed"
          :size="18"
          aria-hidden="true"
        />
        <PanelLeftClose
          v-else
          :size="18"
          aria-hidden="true"
        />
      </button>
      <h1 class="ribbon-bar__title"><I18nText k="training.builder" /></h1>
      <span
        v-if="saveLabel && !readonly"
        class="ribbon-bar__save"
        :class="`is-${saveTone}`"
        :title="saveTitle"
        @click="emit('save')"
      >
        {{ saveLabel }}
      </span>
    </div>
    <div class="ribbon-bar__tabs">
      <div
        class="ribbon-bar__course"
        role="tablist"
        :aria-label="t('training.builder')"
        @keydown="onTabKey"
      >
        <button
          v-for="tab in tabs"
          :id="`builder-ribbon-tab-${tab.id}`"
          :key="tab.id"
          type="button"
          class="ribbon-bar__tab"
          role="tab"
          :class="{ 'is-active': courseTabsActive && active === tab.id }"
          :aria-selected="courseTabsActive && active === tab.id"
          aria-controls="builder-ribbon-panel"
          @click="emit('select', tab.id)"
        >
          <span class="ribbon-bar__inner">
            <span
              class="ribbon-bar__glyph"
              :class="`ribbon-bar__glyph--${tab.id}`"
              aria-hidden="true"
            >
              <component
                :is="tabIcon(tab.id)"
                class="ribbon-bar__glyph-icon"
                :stroke-width="2.4"
              />
            </span>
            <I18nText :k="tab.labelKey" />
          </span>
        </button>
      </div>
      <div
        v-show="canvasHosted"
        :id="BUILDER_CANVAS_TABS_TARGET"
        class="ribbon-bar__canvas-tabs"
      />
    </div>
    <div class="ribbon-bar__actions">
      <ElButton
        text
        class="ribbon-bar__action"
        @click="emit('info')"
      >
        <Info
          :size="15"
          aria-hidden="true"
        />
        <I18nText k="training.builder.info" />
      </ElButton>
      <ElButton
        text
        class="ribbon-bar__action ribbon-bar__action--preview"
        :class="{ 'is-previewing': previewing }"
        @click="emit('preview')"
      >
        <Square
          v-if="previewing"
          :size="15"
          aria-hidden="true"
        />
        <Play
          v-else
          :size="15"
          aria-hidden="true"
        />
        <I18nText
          v-if="previewing"
          k="training.builder.previewExit"
        />
        <I18nText
          v-else
          k="training.builder.preview"
        />
      </ElButton>
    </div>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.ribbon-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  min-height: 2.25rem;
  padding: 0 12px 0 8px;
  background: transparent;
}
.ribbon-bar__lead,
.ribbon-bar__actions {
  display: flex;
  align-items: center;
  align-self: end;
  box-sizing: border-box;
  height: 36px;
  gap: 0.5rem;
  min-width: 0;
}
.ribbon-bar__actions {
  justify-content: flex-end;
}
.ribbon-bar__sidebar {
  display: flex;
  width: 2rem;
  height: 2rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #4b5563;
  cursor: pointer;
}
.ribbon-bar__sidebar:hover {
  background: rgb(255 255 255 / 0.72);
  color: #1f2937;
}
.ribbon-bar__title {
  margin: 0;
  overflow: hidden;
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ribbon-bar__tabs {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  min-width: 0;
}
.ribbon-bar__course,
.ribbon-bar__canvas-tabs {
  display: flex;
  align-items: flex-end;
  min-width: 0;
}
.ribbon-bar__tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  min-width: 3.25rem;
  min-height: 36px;
  margin-top: 6px;
  padding: 4px 14px;
  border: none;
  border-radius: 4px 4px 0 0;
  background: transparent;
  color: #4b5563;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
}
.ribbon-bar__tab:hover:not(.is-active) {
  background: rgb(255 255 255 / 0.7);
  color: #1f2937;
}
.ribbon-bar__tab.is-active {
  position: relative;
  z-index: 3;
  min-height: 44px;
  margin-bottom: -8px;
  padding: 4px 14px 8px;
  border-radius: 10px 10px 0 0;
  background: #fff;
  color: #2563eb;
}
.ribbon-bar__inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ribbon-bar__glyph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 5px;
  color: #fff;
}
.ribbon-bar__glyph-icon {
  width: 12px;
  height: 12px;
}
.ribbon-bar__glyph--slide {
  background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
  box-shadow: 0 1px 2px rgb(37 99 235 / 0.35);
}
.ribbon-bar__glyph--marks {
  background: linear-gradient(135deg, #c084fc 0%, #e879f9 100%);
  box-shadow: 0 1px 2px rgb(192 132 252 / 0.4);
}
.ribbon-bar__glyph--media {
  background: linear-gradient(135deg, #34d399 0%, #22d3ee 100%);
  box-shadow: 0 1px 2px rgb(16 185 129 / 0.4);
}
.ribbon-bar__glyph--steps {
  background: linear-gradient(135deg, #a78bfa 0%, #6366f1 100%);
  box-shadow: 0 1px 2px rgb(99 102 241 / 0.4);
}
.ribbon-bar__glyph--interact {
  background: linear-gradient(135deg, #fb923c 0%, #f43f5e 100%);
  box-shadow: 0 1px 2px rgb(244 63 94 / 0.35);
}
.ribbon-bar__save {
  flex-shrink: 0;
  max-width: min(11rem, 42vw);
  overflow: hidden;
  color: #6b7280;
  font-size: 13px;
  font-weight: 400;
  line-height: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s;
}
.ribbon-bar__save.is-saved:hover {
  color: #374151;
}
.ribbon-bar__save.is-saving {
  color: #3b82f6;
}
.ribbon-bar__save.is-dirty {
  color: #f59e0b;
}
.ribbon-bar__save.is-error {
  color: #b91c1c;
}
.ribbon-bar__actions :deep(.el-button) {
  height: auto;
  min-height: 28px;
  margin: 0;
  padding: 3px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #4b5563;
  font-size: 12px;
  font-weight: 600;
}
.ribbon-bar__actions :deep(.el-button > span) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ribbon-bar__actions :deep(.el-button:hover) {
  background: rgb(255 255 255 / 0.72);
  color: #1f2937;
}
.ribbon-bar__actions :deep(.ribbon-bar__action--preview) {
  color: #15803d;
}
:global(.dark) .ribbon-bar__tab {
  color: #e5e7eb;
}
:global(.dark) .ribbon-bar__tab.is-active {
  background: #1f2937;
  color: #93c5fd;
}
:global(.dark) .ribbon-bar__title,
:global(.dark) .ribbon-bar__sidebar {
  color: #e5e7eb;
}
:global(.dark) .ribbon-bar__sidebar:hover,
:global(.dark) .ribbon-bar__actions :deep(.el-button:hover) {
  background: rgb(255 255 255 / 0.12);
  color: #f9fafb;
}
:global(.dark) .ribbon-bar__save {
  color: #9ca3af;
}
:global(.dark) .ribbon-bar__save.is-saving {
  color: #60a5fa;
}
:global(.dark) .ribbon-bar__save.is-dirty {
  color: #fbbf24;
}
:global(.dark) .ribbon-bar__save.is-saved:hover {
  color: #d1d5db;
}
</style>
