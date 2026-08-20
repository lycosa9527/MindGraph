<script setup lang="ts">
/**
 * Mind-map dedicated toolbar — single-row horizontal flow, lightweight UI.
 */
import { computed, ref } from 'vue'

import { storeToRefs } from 'pinia'

import { ElDropdown, ElTooltip } from 'element-plus'

import {
  ChevronDown,
  Download,
  GitBranchPlus,
  Plus,
  RotateCcw,
  RotateCw,
  Trash2,
  Upload,
} from '@lucide/vue'

import CanvasToolbarMindMapAiGenerate from '@/components/canvas/CanvasToolbarMindMapAiGenerate.vue'
import CanvasToolbarMindMapAudiencePicker from '@/components/canvas/CanvasToolbarMindMapAudiencePicker.vue'
import MindMapAppearanceDropdown from '@/components/canvas/MindMapAppearanceDropdown.vue'
import MindMapExportOptionsPanel from '@/components/canvas/MindMapExportOptionsPanel.vue'
import { useFeatureFlags } from '@/composables'
import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import {
  CANVAS_CLIPBOARD_EXPORT_MENU_ITEM,
  CANVAS_COMMUNITY_EXPORT_MENU_ITEM,
  CANVAS_MINDMAP_EXPORT_MENU_ITEMS,
  CANVAS_WORKSHEET_TEXT_MENU_ITEM,
  CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM,
} from '@/config/canvasExportMenu'
import { useAuthStore, useCanvasExportStore, useDiagramStore } from '@/stores'

import MindMapStructureIcon from './MindMapStructureIcon.vue'

const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity } = useFeatureFlags()
const { triggerImportInPlace } = useDiagramImport()

const showCommunityExport = computed(() => featureCommunity.value && authStore.isAuthenticated)

/** Hidden for now with the ZhiHui sidebar entry; flip when 图示生图 ships. */
const showZhihuiDiagramExport = computed(() => false)

const { handleAddChild, handleAddSibling, handleDeleteNode, handleAddBranch } = useNodeActions({
  registerEventBusListeners: false,
})

const canvasExportStore = useCanvasExportStore()
const { exportOptions, mergedExportOptions } = storeToRefs(canvasExportStore)

const structureDropdownOpen = ref(false)
const exportDropdownOpen = ref(false)

const structureMode = computed(() => {
  void diagramStore.data?.nodes?.length
  void diagramStore.data?.connections?.length
  return diagramStore.getMindMapStructureMode()
})

const structureLabel = computed(() =>
  structureMode.value === 'right'
    ? t('canvas.toolbar.mindMapStructureRight')
    : t('canvas.toolbar.mindMapStructureBalanced')
)

function handleUndo() {
  tryCollabGuardedUndo()
}

function handleRedo() {
  tryCollabGuardedRedo()
}

function handleStructurePick(mode: 'balanced' | 'right') {
  structureDropdownOpen.value = false
  if (diagramStore.setMindMapStructureMode(mode)) {
    notify.success(t('canvas.toolbar.mindMapStructureApplied'))
  }
}

function handleExportCommand(format: string) {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:export_requested', {
    format,
    options: { ...mergedExportOptions.value },
  })
}

function handleZhihuiDiagramMenuClick() {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:zhihui_diagram_requested', {})
}

function handleWorksheetTextMenuClick() {
  exportDropdownOpen.value = false
  eventBus.emit('toolbar:worksheet_text_requested', {})
}

function handleAddChildClick() {
  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId || selectedId === 'topic') {
    handleAddBranch()
    return
  }
  handleAddChild()
}
</script>

<template>
  <div class="mm-toolbar">
    <div class="mm-toolbar__track">
      <!-- Structure mode -->
      <ElTooltip
        :content="structureLabel"
        placement="bottom"
      >
        <span class="inline-flex shrink-0">
          <ElDropdown
            v-model:visible="structureDropdownOpen"
            trigger="hover"
            :show-timeout="150"
            :hide-timeout="200"
            placement="bottom-start"
            popper-class="mm-toolbar-popper mm-toolbar-popper--structure"
          >
            <button
              type="button"
              class="mm-btn mm-btn--structure"
              :aria-label="structureLabel"
            >
              <MindMapStructureIcon
                class="mm-btn__structure-preview"
                :mode="structureMode"
              />
            </button>
            <template #dropdown>
              <div class="mm-panel mm-panel--structure">
                <button
                  type="button"
                  class="mm-structure-card"
                  :class="{ 'is-active': structureMode === 'balanced' }"
                  @click="handleStructurePick('balanced')"
                >
                  <MindMapStructureIcon mode="balanced" />
                  <span class="mm-structure-card__label">{{
                    t('canvas.toolbar.mindMapStructureBalanced')
                  }}</span>
                </button>
                <div class="mm-panel__divider-v" />
                <button
                  type="button"
                  class="mm-structure-card"
                  :class="{ 'is-active': structureMode === 'right' }"
                  @click="handleStructurePick('right')"
                >
                  <MindMapStructureIcon mode="right" />
                  <span class="mm-structure-card__label">{{
                    t('canvas.toolbar.mindMapStructureRight')
                  }}</span>
                </button>
              </div>
            </template>
          </ElDropdown>
        </span>
      </ElTooltip>

      <span class="mm-sep" />

      <!-- Undo / Redo -->
      <div
        class="mm-history-group"
        role="group"
        :aria-label="t('canvas.toolbar.historyGroup')"
      >
        <ElTooltip
          placement="bottom"
          :show-arrow="true"
          popper-class="mm-shortcut-tooltip"
        >
          <template #content>
            <div class="mm-shortcut-tooltip__row">
              <span>{{ t('canvas.toolbar.undo') }}</span>
              <kbd class="mm-shortcut-tooltip__kbd">{{ t('canvas.toolbar.undoShortcut') }}</kbd>
            </div>
          </template>
          <button
            type="button"
            class="mm-history-btn"
            :disabled="!diagramStore.canUndo"
            :aria-label="t('canvas.toolbar.undo')"
            @click="handleUndo"
          >
            <RotateCcw class="mm-history-btn__icon" />
          </button>
        </ElTooltip>
        <ElTooltip
          placement="bottom"
          :show-arrow="true"
          popper-class="mm-shortcut-tooltip"
        >
          <template #content>
            <div class="mm-shortcut-tooltip__row">
              <span>{{ t('canvas.toolbar.redo') }}</span>
              <kbd class="mm-shortcut-tooltip__kbd">{{ t('canvas.toolbar.redoShortcut') }}</kbd>
            </div>
          </template>
          <button
            type="button"
            class="mm-history-btn"
            :disabled="!diagramStore.canRedo"
            :aria-label="t('canvas.toolbar.redo')"
            @click="handleRedo"
          >
            <RotateCw class="mm-history-btn__icon" />
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Node editing -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.addChildNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.addChildNode')"
            @click="handleAddChildClick"
          >
            <Plus class="w-4 h-4 text-blue-500" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('canvas.toolbar.addChildNode') }}</span
            >
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.addSiblingNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.addSiblingNode')"
            @click="handleAddSibling"
          >
            <GitBranchPlus class="w-4 h-4 text-emerald-600" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('canvas.toolbar.addSiblingNode') }}</span
            >
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.deleteNode')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn mm-btn--danger"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.deleteNode')"
            @click="handleDeleteNode"
          >
            <Trash2 class="w-4 h-4" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('canvas.toolbar.deleteNode') }}</span
            >
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Appearance: diagram style + theme color -->
      <MindMapAppearanceDropdown :compact="props.compact" />

      <span class="mm-sep" />

      <CanvasToolbarMindMapAudiencePicker :compact="props.compact" />

      <CanvasToolbarMindMapAiGenerate :compact="props.compact" />

      <span
        v-if="!diagramStore.collabSessionActive"
        class="mm-sep"
      />

      <!-- Import / Export -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.import')"
          placement="bottom"
          :disabled="!props.compact"
        >
          <button
            type="button"
            class="mm-btn"
            :class="{ 'mm-btn--icon': props.compact }"
            :aria-label="t('canvas.toolbar.import')"
            @click="() => triggerImportInPlace()"
          >
            <Upload class="w-4 h-4 text-gray-500" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('canvas.toolbar.import') }}</span
            >
          </button>
        </ElTooltip>

        <div class="mm-export-anchor">
          <ElTooltip
            :content="t('canvas.toolbar.export')"
            placement="bottom"
            :disabled="!props.compact"
          >
            <span class="inline-flex">
              <ElDropdown
                v-model:visible="exportDropdownOpen"
                trigger="click"
                placement="bottom-end"
                popper-class="mm-toolbar-popper mm-toolbar-popper--export"
              >
                <button
                  type="button"
                  class="mm-btn mm-btn--export"
                  :class="{ 'mm-btn--icon': props.compact }"
                  data-learning-sheet-export-anchor
                  data-canvas-export-anchor
                  :aria-label="t('canvas.toolbar.export')"
                >
                  <Download class="w-4 h-4 text-amber-300" />
                  <span
                    v-if="!props.compact"
                    class="mm-btn__label"
                    >{{ t('canvas.toolbar.export') }}</span
                  >
                  <ChevronDown
                    v-if="!props.compact"
                    class="mm-btn__chevron mm-btn__chevron--on-dark"
                  />
                </button>
                <template #dropdown>
                  <div class="mm-panel mm-panel--export">
                    <MindMapExportOptionsPanel v-model="exportOptions" />
                    <div class="mm-panel mm-panel--list mm-panel--export-formats">
                      <button
                        type="button"
                        class="mm-list-item"
                        @click="handleExportCommand(CANVAS_CLIPBOARD_EXPORT_MENU_ITEM.command)"
                      >
                        {{ t(CANVAS_CLIPBOARD_EXPORT_MENU_ITEM.labelKey) }}
                      </button>
                      <button
                        type="button"
                        class="mm-list-item"
                        @click="handleWorksheetTextMenuClick"
                      >
                        {{ t(CANVAS_WORKSHEET_TEXT_MENU_ITEM.labelKey) }}
                      </button>
                      <button
                        v-for="item in CANVAS_MINDMAP_EXPORT_MENU_ITEMS"
                        :key="item.command"
                        type="button"
                        class="mm-list-item"
                        :class="{ 'mm-list-item--divided': item.divided }"
                        @click="handleExportCommand(item.command)"
                      >
                        {{ t(item.labelKey) }}
                      </button>
                      <button
                        v-if="showZhihuiDiagramExport"
                        type="button"
                        class="mm-list-item"
                        :class="{
                          'mm-list-item--divided': CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.divided,
                        }"
                        @click="handleZhihuiDiagramMenuClick"
                      >
                        {{ t(CANVAS_ZHIHUI_DIAGRAM_MENU_ITEM.labelKey) }}
                      </button>
                      <button
                        v-if="showCommunityExport"
                        type="button"
                        class="mm-list-item"
                        :class="{
                          'mm-list-item--divided': CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided,
                        }"
                        @click="handleExportCommand(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command)"
                      >
                        {{ t(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey) }}
                      </button>
                    </div>
                  </div>
                </template>
              </ElDropdown>
            </span>
          </ElTooltip>
        </div>
      </div>
    </div>
  </div>
</template>

<style src="./mindMapToolbarButtons.css"></style>
<style scoped src="./canvasToolbarMindMap.css"></style>
<style src="./canvasToolbarMindMapPopper.css"></style>
