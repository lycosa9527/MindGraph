<script setup lang="ts">
/**
 * Mind-map dedicated toolbar — single-row horizontal flow, lightweight UI.
 */
import { computed, ref } from 'vue'

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
  Wand2,
} from '@lucide/vue'

import MindMapAppearanceDropdown from '@/components/canvas/MindMapAppearanceDropdown.vue'

import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { useCanvasReset } from '@/composables/canvasPage/useCanvasReset'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar'
import { useFeatureFlags } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { CANVAS_STANDARD_EXPORT_MENU_ITEMS, CANVAS_COMMUNITY_EXPORT_MENU_ITEM } from '@/config/canvasExportMenu'
import { useAuthStore, useDiagramStore } from '@/stores'

import MindMapStructureIcon from './MindMapStructureIcon.vue'

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity } = useFeatureFlags()
const { triggerImportInPlace } = useDiagramImport()

const showCommunityExport = computed(
  () => featureCommunity.value && authStore.isAuthenticated
)

const { handleAddChild, handleAddSibling, handleDeleteNode, handleAddBranch } = useNodeActions({
  registerEventBusListeners: false,
})

const { isAIGenerating, handleAIGenerate } = useCanvasToolbarApps()
const { resetToDefaultTemplate } = useCanvasReset()

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
  eventBus.emit('toolbar:export_requested', { format })
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
          class="mm-btn mm-btn--select"
          :aria-label="structureLabel"
        >
          <MindMapStructureIcon
            class="mm-btn__structure-preview"
            :mode="structureMode"
          />
          <span class="mm-btn__label">{{ structureLabel }}</span>
          <ChevronDown class="mm-btn__chevron" />
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

      <span class="mm-sep" />

      <!-- Undo / Redo — combined control; reset as text button -->
      <div class="mm-history-wrap">
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
        <ElTooltip
          :content="t('canvas.topBar.resetTemplate')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--reset"
            :aria-label="t('canvas.topBar.reset')"
            @click="resetToDefaultTemplate"
          >
            {{ t('canvas.topBar.reset') }}
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Node editing -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.addChildNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn"
            @click="handleAddChildClick"
          >
            <Plus class="w-4 h-4 text-blue-500" />
            <span class="mm-btn__label">{{ t('canvas.toolbar.addChildNode') }}</span>
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.addSiblingNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn"
            @click="handleAddSibling"
          >
            <GitBranchPlus class="w-4 h-4 text-emerald-600" />
            <span class="mm-btn__label">{{ t('canvas.toolbar.addSiblingNode') }}</span>
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.deleteNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--danger"
            @click="handleDeleteNode"
          >
            <Trash2 class="w-4 h-4" />
            <span class="mm-btn__label">{{ t('canvas.toolbar.deleteNode') }}</span>
          </button>
        </ElTooltip>
      </div>

      <span class="mm-sep" />

      <!-- Appearance: diagram style + theme color -->
      <MindMapAppearanceDropdown />

      <span class="mm-sep" />

      <!-- AI generate -->
      <ElTooltip
        v-if="!diagramStore.collabSessionActive"
        :content="
          isAIGenerating
            ? t('canvas.toolbar.aiGenerating')
            : t('canvas.toolbar.aiGenerateTooltip')
        "
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn mm-btn--ai"
          :disabled="isAIGenerating"
          @click="() => handleAIGenerate()"
        >
          <Wand2 class="h-4 w-4 shrink-0 text-white" />
          <span class="mm-btn__label">{{
            isAIGenerating ? t('canvas.toolbar.aiGenerating') : t('canvas.toolbar.aiGenerate')
          }}</span>
        </button>
      </ElTooltip>

      <span
        v-if="!diagramStore.collabSessionActive"
        class="mm-sep"
      />

      <!-- Import / Export -->
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.import')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn"
            @click="() => triggerImportInPlace()"
          >
            <Upload class="w-4 h-4 text-gray-500" />
            <span class="mm-btn__label">{{ t('canvas.toolbar.import') }}</span>
          </button>
        </ElTooltip>

        <div class="mm-export-anchor">
          <ElDropdown
            v-model:visible="exportDropdownOpen"
            trigger="click"
            placement="bottom-end"
            popper-class="mm-toolbar-popper"
          >
            <button
              type="button"
              class="mm-btn mm-btn--export"
              data-learning-sheet-export-anchor
              data-canvas-export-anchor
            >
              <Download class="w-4 h-4 text-amber-300" />
              <span class="mm-btn__label">{{ t('canvas.toolbar.export') }}</span>
              <ChevronDown class="mm-btn__chevron mm-btn__chevron--on-dark" />
            </button>
            <template #dropdown>
              <div class="mm-panel mm-panel--list">
                <button
                  v-for="item in CANVAS_STANDARD_EXPORT_MENU_ITEMS"
                  :key="item.command"
                  type="button"
                  class="mm-list-item"
                  :class="{ 'mm-list-item--divided': item.divided }"
                  @click="handleExportCommand(item.command)"
                >
                  {{ t(item.labelKey) }}
                </button>
                <button
                  v-if="showCommunityExport"
                  type="button"
                  class="mm-list-item"
                  :class="{ 'mm-list-item--divided': CANVAS_COMMUNITY_EXPORT_MENU_ITEM.divided }"
                  @click="handleExportCommand(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.command)"
                >
                  {{ t(CANVAS_COMMUNITY_EXPORT_MENU_ITEM.labelKey) }}
                </button>
              </div>
            </template>
          </ElDropdown>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mm-toolbar {
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.mm-toolbar__track {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  min-width: min-content;
  max-width: 100%;
  padding: 2px 4px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}

.mm-toolbar__track::-webkit-scrollbar {
  height: 4px;
}

.mm-toolbar__track::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}

.mm-sep {
  flex-shrink: 0;
  width: 1px;
  height: 20px;
  margin: 0 2px;
  background: #e5e7eb;
}

:global(.dark) .mm-sep {
  background: #4b5563;
}

.mm-btn-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.mm-export-anchor {
  position: relative;
  flex-shrink: 0;
}

.mm-history-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mm-history-group {
  display: inline-flex;
  align-items: stretch;
  height: 32px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

:global(.dark) .mm-history-group {
  background: #1f2937;
  border-color: #374151;
  box-shadow: none;
}

.mm-history-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 100%;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.mm-history-btn + .mm-history-btn {
  border-left: 1px solid #e5e7eb;
}

:global(.dark) .mm-history-btn + .mm-history-btn {
  border-left-color: #374151;
}

.mm-history-btn:hover:not(:disabled) {
  background: #f9fafb;
  color: #6b7280;
}

:global(.dark) .mm-history-btn:hover:not(:disabled) {
  background: #374151;
  color: #d1d5db;
}

.mm-history-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.mm-history-btn__icon {
  width: 16px;
  height: 16px;
}

.mm-btn--reset {
  min-width: 52px;
  padding: 0 12px;
  font-weight: 500;
  color: #6b7280;
  background: #fff;
  border-color: #e5e7eb;
}

.mm-btn--reset:hover:not(:disabled) {
  color: #374151;
  background: #f9fafb;
  border-color: #d1d5db;
}

:global(.dark) .mm-btn--reset {
  color: #9ca3af;
  background: #1f2937;
  border-color: #374151;
}

:global(.dark) .mm-btn--reset:hover:not(:disabled) {
  color: #e5e7eb;
  background: #374151;
  border-color: #4b5563;
}

.mm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

:global(.dark) .mm-btn {
  background: #1f2937;
  border-color: #374151;
  color: #e5e7eb;
  box-shadow: none;
}

.mm-btn:hover:not(:disabled) {
  background: #f9fafb;
  border-color: #d1d5db;
}

.mm-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.mm-btn--icon {
  width: 32px;
  padding: 0;
}

.mm-btn--select {
  max-width: 168px;
}

.mm-btn--danger {
  color: #dc2626;
  border-color: #fecaca;
}

.mm-btn--danger:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #fca5a5;
}

.mm-btn--ai {
  border: none;
  color: #fff;
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  box-shadow:
    0 1px 3px rgb(37 99 235 / 0.35),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
}

.mm-btn--ai:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
  border-color: transparent;
  box-shadow:
    0 2px 8px rgb(37 99 235 / 0.4),
    inset 0 1px 0 rgb(255 255 255 / 0.2);
}

.mm-btn--ai .mm-btn__label {
  color: #fff;
}

:global(.dark) .mm-btn--ai {
  background: linear-gradient(180deg, rgb(59 130 246) 0%, rgb(37 99 235) 100%);
  border: none;
  color: #fff;
}

:global(.dark) .mm-btn--ai:hover:not(:disabled) {
  background: linear-gradient(180deg, rgb(37 99 235) 0%, rgb(29 78 216) 100%);
}

.mm-btn--export {
  background: #1e293b;
  border-color: #1e293b;
  color: #fff;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.25);
}

.mm-btn--export:hover:not(:disabled) {
  background: #0f172a;
  border-color: #0f172a;
}

.mm-btn__label {
  font-weight: 500;
}

.mm-btn__label--truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 96px;
}

.mm-btn__structure-preview {
  width: 36px !important;
  height: 22px !important;
}

.mm-btn__chevron {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: #9ca3af;
}

.mm-btn__chevron--on-dark {
  color: rgb(255 255 255 / 0.65);
}
</style>

<!-- Teleported dropdown panels — isolated from global Element Plus styles -->
<style>
.mm-toolbar-popper.el-popper {
  padding: 0 !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 12px !important;
  background: #fff !important;
  box-shadow:
    0 4px 16px rgb(15 23 42 / 0.08),
    0 1px 4px rgb(15 23 42 / 0.04) !important;
  overflow: hidden !important;
}

.mm-toolbar-popper.el-popper .el-popper__arrow::before {
  border-color: #e5e7eb !important;
  background: #fff !important;
}

.dark .mm-toolbar-popper.el-popper {
  border-color: #374151 !important;
  background: #1f2937 !important;
  box-shadow:
    0 4px 16px rgb(0 0 0 / 0.35),
    0 1px 4px rgb(0 0 0 / 0.2) !important;
}

.dark .mm-toolbar-popper.el-popper .el-popper__arrow::before {
  border-color: #374151 !important;
  background: #1f2937 !important;
}

.mm-panel {
  box-sizing: border-box;
}

.mm-panel--structure {
  display: flex;
  align-items: stretch;
  padding: 8px;
  gap: 0;
}

.mm-panel__divider-v {
  width: 1px;
  margin: 4px 6px;
  background: #e5e7eb;
  flex-shrink: 0;
}

.dark .mm-panel__divider-v {
  background: #374151;
}

.mm-structure-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 108px;
  padding: 10px 12px 8px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.mm-structure-card:hover {
  background: #f3f4f6;
}

.mm-structure-card.is-active {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.dark .mm-structure-card:hover {
  background: #374151;
}

.dark .mm-structure-card.is-active {
  background: #1e3a5f;
  border-color: #3b82f6;
}

.mm-structure-card__label {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  text-align: center;
  line-height: 1.3;
  white-space: nowrap;
}

.dark .mm-structure-card__label {
  color: #e5e7eb;
}

.mm-panel--list {
  display: flex;
  flex-direction: column;
  padding: 4px;
  min-width: 160px;
}

.mm-panel--scrollable {
  max-height: min(420px, 70vh);
  overflow-y: auto;
}

.mm-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #374151;
  font-size: 12px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.mm-list-item:hover {
  background: #f3f4f6;
}

.mm-list-item.is-active {
  background: #eff6ff;
  color: #2563eb;
}

.mm-list-item--divided {
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid #f3f4f6;
}

.dark .mm-list-item {
  color: #e5e7eb;
}

.dark .mm-list-item:hover {
  background: #374151;
}

.dark .mm-list-item.is-active {
  background: #1e3a5f;
  color: #93c5fd;
}

.mm-theme-swatch {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  border: 1px solid rgb(0 0 0 / 0.08);
  flex-shrink: 0;
}

.mm-list-item__label {
  flex: 1;
  min-width: 0;
}

.mm-toolbar-popper--apps {
  width: min(300px, calc(100vw - 24px)) !important;
}

.mm-panel--apps {
  display: flex;
  flex-direction: column;
  padding: 4px;
  max-height: min(420px, 70vh);
  overflow-y: auto;
}

.mm-app-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s ease;
}

.mm-app-item:hover {
  background: #f3f4f6;
}

.dark .mm-app-item:hover {
  background: #374151;
}

.mm-app-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.mm-app-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.mm-app-item__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.dark .mm-app-item__title {
  color: #f9fafb;
}

.mm-app-item__tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 9999px;
  background: #f3f4f6;
  color: #6b7280;
}

.mm-app-item__desc {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.35;
}

.dark .mm-app-item__desc {
  color: #9ca3af;
}

.mm-shortcut-tooltip.el-popper {
  padding: 6px 10px !important;
  border: none !important;
  border-radius: 8px !important;
  background: #1e1e20 !important;
  box-shadow: 0 4px 12px rgb(0 0 0 / 0.28) !important;
}

.mm-shortcut-tooltip.el-popper .el-popper__arrow::before {
  border-color: #1e1e20 !important;
  background: #1e1e20 !important;
}

.mm-shortcut-tooltip__row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  color: #fff;
  white-space: nowrap;
}

.mm-shortcut-tooltip__kbd {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border: none;
  border-radius: 6px;
  background: #3e3e42;
  color: #fff;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
</style>
