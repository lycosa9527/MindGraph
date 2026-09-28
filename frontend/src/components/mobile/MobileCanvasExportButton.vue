<script setup lang="ts">
/**
 * Mobile canvas export — desktop export commands in a bottom sheet.
 * Mind maps include color/answer options, clipboard, and worksheet text.
 * Other diagrams use the standard PNG / SVG / PDF / .mg menu.
 */
import { type Component, computed, ref } from 'vue'

import { storeToRefs } from 'pinia'

import {
  ClipboardCopy,
  Download,
  FileImage,
  FileJson,
  FilePen,
  FileText,
  ImageDown,
  Share2,
} from '@lucide/vue'

import MindMapExportOptionsPanel from '@/components/canvas/MindMapExportOptionsPanel.vue'
import MindMapLearningSheetIcon from '@/components/canvas/MindMapLearningSheetIcon.vue'
import { useFeatureFlags, useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import {
  CANVAS_CLIPBOARD_EXPORT_MENU_ITEM,
  CANVAS_COMMUNITY_EXPORT_MENU_ITEM,
  CANVAS_MINDMAP_EXPORT_MENU_ITEMS,
  CANVAS_STANDARD_EXPORT_MENU_ITEMS,
  CANVAS_WORKSHEET_TEXT_MENU_ITEM,
} from '@/config/canvasExportMenu'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useCanvasExportStore } from '@/stores/canvasExport'
import { isPdfExportCommand } from '@/utils/diagramPdfExport'

const props = defineProps<{
  mindMapExport: boolean
}>()

const open = ref(false)
const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity } = useFeatureFlags()
const canvasExportStore = useCanvasExportStore()
const { exportOptions, mergedExportOptions } = storeToRefs(canvasExportStore)

const showCommunityExport = computed(() => featureCommunity.value && authStore.isAuthenticated)

const formatItems = computed(() =>
  props.mindMapExport ? CANVAS_MINDMAP_EXPORT_MENU_ITEMS : CANVAS_STANDARD_EXPORT_MENU_ITEMS
)

function formatIcon(command: string): Component {
  if (command === 'png') return ImageDown
  if (command === 'svg') return FileImage
  if (isPdfExportCommand(command)) return FileText
  if (command === 'mg') return FileJson
  if (command === 'clipboard') return ClipboardCopy
  return Download
}

function handleExportCommand(format: string): void {
  open.value = false
  eventBus.emit('toolbar:export_requested', {
    format,
    options: { ...mergedExportOptions.value },
  })
}

function handleWorksheetText(): void {
  open.value = false
  eventBus.emit('toolbar:worksheet_text_requested', {})
}

function handleMakeLearningSheet(): void {
  open.value = false
  if (!diagramStore.data?.nodes?.length) {
    notify.warning(t('canvas.toolbar.createDiagramFirst'))
    return
  }
  eventBus.emit('toolbar:worksheet_text_requested', { preferLearningSheet: true })
}
</script>

<template>
  <button
    type="button"
    class="bottom-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 active:bg-gray-200 transition-colors"
    :aria-label="t('canvas.toolbar.export')"
    @click="open = true"
  >
    <Download
      :size="16"
      class="text-gray-700"
    />
    <span class="text-xs font-medium text-gray-700"><I18nText k="canvas.toolbar.export" /></span>
  </button>

  <Teleport to="body">
    <Transition name="model-sheet">
      <div
        v-if="open"
        class="model-sheet-overlay"
        @click.self="open = false"
      >
        <div
          class="model-sheet-panel mobile-export-sheet"
          role="dialog"
          :aria-label="t('canvas.toolbar.export')"
        >
          <div class="model-sheet-handle" />
          <div class="px-4 pt-3 pb-1 text-sm font-semibold text-gray-800">
            <I18nText k="canvas.toolbar.export" />
          </div>

          <MindMapExportOptionsPanel
            v-if="mindMapExport"
            v-model="exportOptions"
            stack
          />

          <div class="mobile-export-list">
            <button
              v-if="mindMapExport"
              type="button"
              class="mobile-export-row"
              @click="handleExportCommand(CANVAS_CLIPBOARD_EXPORT_MENU_ITEM.command)"
            >
              <ClipboardCopy
                :size="18"
                class="shrink-0 text-gray-500"
              />
              <span><I18nText :k="CANVAS_CLIPBOARD_EXPORT_MENU_ITEM.labelKey" /></span>
            </button>
            <button
              v-if="mindMapExport"
              type="button"
              class="mobile-export-row"
              @click="handleMakeLearningSheet"
            >
              <MindMapLearningSheetIcon kind="worksheet" />
              <span><I18nText k="canvas.ribbon.makeLearningSheet" /></span>
            </button>
            <button
              v-if="mindMapExport"
              type="button"
              class="mobile-export-row"
              @click="handleWorksheetText"
            >
              <FilePen
                :size="18"
                class="shrink-0 text-gray-500"
              />
              <span><I18nText :k="CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey" /></span>
            </button>
            <button
              v-for="item in formatItems"
              :key="item.command"
              type="button"
              class="mobile-export-row"
              :class="{ 'mobile-export-row--divided': item.divided }"
              @click="handleExportCommand(item.command)"
            >
              <component
                :is="formatIcon(item.command)"
                :size="18"
                class="shrink-0 text-gray-500"
              />
              <span><I18nText :k="item.labelKey" /></span>
            </button>
            <button
              v-if="showCommunityExport"
              type="button"
              class="mobile-export-row mobile-export-row--divided"
              @click="handleExportCommand(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command)"
            >
              <Share2
                :size="18"
                class="shrink-0 text-rose-500"
              />
              <span><I18nText :k="CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey" /></span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.mobile-export-sheet {
  max-height: min(90dvh, 640px);
  overflow-y: auto;
}

.mobile-export-list {
  display: flex;
  flex-direction: column;
  padding: 4px 8px 8px;
}

.mobile-export-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  padding: 10px 12px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: #1c1917;
  font-size: 15px;
  font-weight: 500;
  text-align: start;
}

.mobile-export-row:active {
  background: #f5f5f4;
}

.mobile-export-row--divided {
  margin-top: 4px;
  border-top: 1px solid #e7e5e4;
  border-radius: 0 0 12px 12px;
}
</style>
