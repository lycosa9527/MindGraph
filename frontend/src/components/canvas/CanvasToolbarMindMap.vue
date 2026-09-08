<script setup lang="ts">
/**
 * Mind-map dedicated toolbar — single-row horizontal flow, lightweight UI.
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { storeToRefs } from 'pinia'

import { ElDropdown, ElTooltip } from 'element-plus'

import {
  Bot,
  ChevronDown,
  Download,
  FileText,
  GitBranch,
  LayoutGrid,
  Lightbulb,
  Link2,
  MessageSquare,
  Mic,
  MonitorPlay,
  Paintbrush,
  RotateCcw,
  RotateCw,
  Save,
  School,
  Sparkles,
  Trash2,
  Upload,
} from '@lucide/vue'

import MindMapAppearanceDropdown from '@/components/canvas/MindMapAppearanceDropdown.vue'
import MindMapExportOptionsPanel from '@/components/canvas/MindMapExportOptionsPanel.vue'
import MindMapNumberingControls from '@/components/canvas/MindMapNumberingControls.vue'
import CanvasToolbarMindMapFormat from '@/components/canvas/CanvasToolbarMindMapFormat.vue'
import CanvasToolbarMindMapInsert from '@/components/canvas/CanvasToolbarMindMapInsert.vue'
import CanvasToolbarMindMapNodeStyle from '@/components/canvas/CanvasToolbarMindMapNodeStyle.vue'
import MindMapInsertNodeIcon from '@/components/canvas/MindMapInsertNodeIcon.vue'
import MindMapLearningSheetIcon from '@/components/canvas/MindMapLearningSheetIcon.vue'
import { useFeatureFlags } from '@/composables'
import { useCanvasReset } from '@/composables/canvasPage/useCanvasReset'
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
import { DOC_SUMMARY_LITE_UI } from '@/config/docSummaryLite'
import { docSummaryLiteIntent } from '@/composables/mindMap/useDocSummaryLiteSaveAndGenerate'
import {
  useAuthStore,
  useCanvasExportStore,
  useDiagramStore,
  useMindClassroomStore,
  useVoiceNotesStore,
} from '@/stores'

import { useMindMapRibbonActions } from '@/canvas-ribbon/useMindMapRibbonActions'
import type { MindMapRibbonTabId } from '@/canvas-ribbon/mindMapRibbonTypes'
import { useCanvasToolbarFormatting, useFollowNodeStyleToolbar } from '@/composables/canvasToolbar'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'

import MindMapStructureIcon from './MindMapStructureIcon.vue'

const props = withDefaults(
  defineProps<{ compact?: boolean; ribbonTab?: MindMapRibbonTabId }>(),
  { compact: false, ribbonTab: 'edit' }
)

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const authStore = useAuthStore()
const { featureCommunity } = useFeatureFlags()
const { triggerImportInPlace } = useDiagramImport()
const { resetToDefaultTemplate } = useCanvasReset()
const ribbon = useMindMapRibbonActions()
const classroomStore = useMindClassroomStore()
const voiceNotesStore = useVoiceNotesStore()
const route = useRoute()
const { activeTool, handleToolSelect, openTool } = useMindMapSideToolbarState()

const showCommunityExport = computed(() => featureCommunity.value && authStore.isAuthenticated)

/** Hidden for now with the ZhiHui sidebar entry; flip when 图示生图 ships. */
const showZhihuiDiagramExport = computed(() => false)

const { handleAddChild, handleAddSibling, handleDeleteNode, handleAddBranch } = useNodeActions({
  registerEventBusListeners: false,
})

const { formatBrushActive, formatBrushLocked, handleFormatBrush } = useCanvasToolbarFormatting()
const { followEnabled, setFollowEnabled } = useFollowNodeStyleToolbar()

const canvasExportStore = useCanvasExportStore()
const { exportOptions, mergedExportOptions } = storeToRefs(canvasExportStore)

const structureDropdownOpen = ref(false)
const exportDropdownOpen = ref(false)
const trackRef = ref<HTMLElement | null>(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)
const trackOverflowing = computed(() => canScrollLeft.value || canScrollRight.value)
let trackResizeObserver: ResizeObserver | null = null

function updateTrackOverflow(): void {
  const el = trackRef.value
  if (!el) {
    canScrollLeft.value = false
    canScrollRight.value = false
    return
  }
  const maxScroll = el.scrollWidth - el.clientWidth
  canScrollLeft.value = el.scrollLeft > 1
  canScrollRight.value = maxScroll - el.scrollLeft > 1
}

function scrollTrack(direction: -1 | 1): void {
  const el = trackRef.value
  if (!el) return
  const delta = Math.max(160, Math.round(el.clientWidth * 0.45))
  el.scrollBy({ left: direction * delta, behavior: 'smooth' })
}

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

function requireNodeSelection(action: () => void): void {
  if (ribbon.hasSelection) {
    action()
    return
  }
  notify.warning(t('canvas.toolbar.selectNodesFirst'))
}

function onFormatPainterClick(): void {
  if (formatBrushActive.value) {
    handleFormatBrush()
    return
  }
  requireNodeSelection(handleFormatBrush)
}

function onFormatPainterDblClick(): void {
  if (formatBrushActive.value) {
    handleFormatBrush({ lock: true })
    return
  }
  requireNodeSelection(() => handleFormatBrush({ lock: true }))
}

function onFollowChange(value: string | number | boolean): void {
  setFollowEnabled(Boolean(value))
}

function onRestoreLearningSheet(): void {
  ribbon.learningSheet.exitLearningSheet()
}

function handleAddChildClick() {
  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId || selectedId === 'topic') {
    handleAddBranch()
    return
  }
  handleAddChild()
}

async function handleReset() {
  await resetToDefaultTemplate()
}

function openDocGenerate(kind: 'file' | 'web'): void {
  docSummaryLiteIntent.value = kind === 'web' ? 'web' : 'doc'
  const tab = kind === 'web' ? 'web' : DOC_SUMMARY_LITE_UI ? 'file' : 'document'
  openTool('document_summary')
  eventBus.emit('mindmap:doc_summary_tab', { tab })
}

function openVoiceSummary(): void {
  voiceNotesStore.openModal()
}

function openClassroom(): void {
  classroomStore.openModal()
}

onMounted(() => {
  const openDocSummary =
    route.query.openDocSummary === '1' || route.query.openFileCenter === '1'
  if (openDocSummary && activeTool.value === null) {
    openTool('document_summary')
  }
  const el = trackRef.value
  if (el && typeof ResizeObserver !== 'undefined') {
    trackResizeObserver = new ResizeObserver(() => updateTrackOverflow())
    trackResizeObserver.observe(el)
    if (el.parentElement) {
      trackResizeObserver.observe(el.parentElement)
    }
  }
  updateTrackOverflow()
})

onUnmounted(() => {
  trackResizeObserver?.disconnect()
  trackResizeObserver = null
})

watch(
  () => props.ribbonTab,
  async () => {
    await nextTick()
    trackRef.value?.scrollTo({ left: 0 })
    updateTrackOverflow()
  }
)
</script>

<template>
  <div
    class="mm-toolbar"
    :class="{ 'is-overflowing': trackOverflowing }"
  >
    <button
      v-show="trackOverflowing"
      type="button"
      class="mm-toolbar__nudge mm-toolbar__nudge--left"
      :disabled="!canScrollLeft"
      :aria-label="t('canvas.mindMapSlideOverlay.prev')"
      @click="scrollTrack(-1)"
    >
      <span
        class="mm-toolbar__nudge-tri"
        aria-hidden="true"
      />
    </button>
    <div
      ref="trackRef"
      class="mm-toolbar__track"
      :class="{
        'mm-toolbar__track--edit-dense': ribbonTab === 'edit',
        'is-overflowing': trackOverflowing,
      }"
      @scroll.passive="updateTrackOverflow"
    >
      <template v-if="ribbonTab === 'edit'">
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
              <ChevronDown
                :size="12"
                class="mm-btn__chevron"
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
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('canvas.toolbar.addChildNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--icon"
            :class="{ 'is-dimmed': !ribbon.hasSelection }"
            :aria-disabled="!ribbon.hasSelection"
            :aria-label="t('canvas.toolbar.addChildNode')"
            @click="requireNodeSelection(handleAddChildClick)"
          >
            <MindMapInsertNodeIcon kind="child" />
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.addSiblingNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--icon"
            :class="{ 'is-dimmed': !ribbon.hasSelection }"
            :aria-disabled="!ribbon.hasSelection"
            :aria-label="t('canvas.toolbar.addSiblingNode')"
            @click="requireNodeSelection(handleAddSibling)"
          >
            <MindMapInsertNodeIcon kind="sibling" />
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.toolbar.deleteNode')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--danger mm-btn--icon"
            :class="{ 'is-dimmed': !ribbon.hasSelection }"
            :aria-disabled="!ribbon.hasSelection"
            :aria-label="t('canvas.toolbar.deleteNode')"
            @click="requireNodeSelection(handleDeleteNode)"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </ElTooltip>
        <ElTooltip
          :content="t('canvas.topBar.resetTemplate')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--icon"
            :aria-label="t('canvas.topBar.resetCanvas')"
            @click="handleReset"
          >
            <RotateCcw class="w-4 h-4" />
          </button>
        </ElTooltip>
      </div>
      </template>

      <template v-if="ribbonTab === 'edit'">
        <ElTooltip
          :content="t('canvas.toolbar.formatPainter')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn mm-btn--icon"
            :class="{
              'is-active': formatBrushActive,
              'is-locked': formatBrushLocked,
              'is-dimmed': !ribbon.hasSelection && !formatBrushActive,
            }"
            :aria-disabled="!ribbon.hasSelection && !formatBrushActive"
            :aria-label="t('canvas.toolbar.formatPainter')"
            :aria-pressed="formatBrushActive"
            @click="onFormatPainterClick"
            @dblclick.prevent="onFormatPainterDblClick"
          >
            <Paintbrush class="w-4 h-4" />
          </button>
        </ElTooltip>
        <span class="mm-sep" />
        <CanvasToolbarMindMapNodeStyle
          compact
          :disabled="!ribbon.hasSelection"
        />
        <span class="mm-sep" />
        <CanvasToolbarMindMapFormat
          hide-painter
          compact
          :disabled="!ribbon.hasSelection"
        />
        <span class="mm-sep" />
        <MindMapAppearanceDropdown compact />
        <span class="mm-sep" />
        <MindMapNumberingControls
          variant="button"
          compact
        />
      </template>

      <template v-if="ribbonTab === 'edit'">
        <span class="mm-sep" />
        <CanvasToolbarMindMapInsert />
        <span class="mm-sep" />
        <ElTooltip
          :content="t('canvas.toolbar.nodeStyleFollowHint')"
          placement="bottom"
        >
          <span class="inline-flex shrink-0">
            <label
              class="mm-follow-toggle"
              data-testid="mindmap-node-style-follow"
            >
              <span class="mm-follow-toggle__label">{{ t('canvas.toolbar.nodeStyleFollow') }}</span>
              <el-switch
                :model-value="followEnabled"
                size="small"
                :aria-label="t('canvas.toolbar.nodeStyleFollow')"
                @change="onFollowChange"
              />
            </label>
          </span>
        </ElTooltip>
      </template>

      <template v-if="ribbonTab === 'file'">
      <div class="mm-btn-group">
        <ElTooltip
          :content="t('common.save')"
          placement="bottom"
        >
          <button
            type="button"
            class="mm-btn"
            :aria-label="t('common.save')"
            @click="ribbon.requestSave"
          >
            <Save class="w-4 h-4" />
            <span
              v-if="!props.compact"
              class="mm-btn__label"
              >{{ t('common.save') }}</span
            >
          </button>
        </ElTooltip>
      </div>
      <span class="mm-sep" />
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
            <Upload class="w-4 h-4" />
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
                  <Download class="w-4 h-4" />
                  <span
                    v-if="!props.compact"
                    class="mm-btn__label"
                    >{{ t('canvas.toolbar.export') }}</span
                  >
                  <ChevronDown
                    v-if="!props.compact"
                    :size="12"
                    class="mm-btn__chevron"
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
      </template>

      <template v-if="ribbonTab === 'teaching'">
          <div class="mm-btn-group">
            <ElTooltip
              :content="t('canvas.mindMapSideToolbar.learningSheet')"
              placement="bottom"
            >
              <button
                type="button"
                class="mm-btn mm-ls-entry"
                :class="{
                  'mm-btn--icon': props.compact && !ribbon.learningSheet.isLearningSheetActive,
                  'is-active':
                    activeTool === 'learning_sheet' ||
                    ribbon.learningSheet.isPickActive ||
                    ribbon.learningSheet.isLearningSheetActive,
                  'is-expanded': ribbon.learningSheet.isLearningSheetActive,
                }"
                :aria-label="t('canvas.mindMapSideToolbar.learningSheet')"
                @click="ribbon.openSideTool('learning_sheet')"
              >
                <MindMapLearningSheetIcon kind="blanks" />
                <span
                  v-if="!props.compact"
                  class="mm-btn__label"
                  >{{ t('canvas.mindMapSideToolbar.learningSheet') }}</span
                >
                <span
                  v-if="ribbon.learningSheet.isLearningSheetActive"
                  class="mm-ls-restore"
                  role="button"
                  tabindex="0"
                  :aria-label="t('canvas.mindMapSideToolbar.restoreFullDiagram')"
                  @click.stop="onRestoreLearningSheet"
                  @keydown.enter.stop="onRestoreLearningSheet"
                  @keydown.space.prevent.stop="onRestoreLearningSheet"
                >
                  {{ t('canvas.mindMapSideToolbar.restoreFullDiagram') }}
                </span>
              </button>
            </ElTooltip>
          <ElTooltip
            :content="t('canvas.ribbon.makeLearningSheet')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.ribbon.makeLearningSheet')"
              data-learning-sheet-nudge-anchor
              @click="() => ribbon.requestWorksheetText(true)"
            >
              <MindMapLearningSheetIcon kind="worksheet" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.makeLearningSheet') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.zoomControls.presentationMode')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.zoomControls.presentationMode')"
              @click="ribbon.startPresentation"
            >
              <MonitorPlay class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.zoomControls.presentationMode') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.floatingToolbar.explain')"
            placement="bottom"
            :disabled="!props.compact"
          >
            <button
              type="button"
              class="mm-btn"
              :aria-disabled="!ribbon.hasSelection"
              :class="{ 'is-dimmed': !ribbon.hasSelection }"
              :aria-label="t('canvas.floatingToolbar.explain')"
              @click="requireNodeSelection(() => ribbon.requestExplainNode())"
            >
              <Lightbulb class="w-4 h-4" />
              <span class="mm-btn__label">{{ t('canvas.floatingToolbar.explain') }}</span>
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.mindMapSideToolbar.mindClassroom')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.mindMapSideToolbar.mindClassroom')"
              @click="openClassroom"
            >
              <School class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.mindMapSideToolbar.mindClassroom') }}</span
              >
            </button>
          </ElTooltip>
        </div>
      </template>

      <template v-if="ribbonTab === 'ai'">
        <div class="mm-btn-group">
          <ElTooltip
            :content="t('canvas.ribbon.topicGenerate')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.ribbon.topicGenerate')"
              @click="ribbon.handleAIGenerate()"
            >
              <Sparkles class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.topicGenerate') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.ribbon.docGenerate')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{
                'mm-btn--icon': props.compact,
                'is-active': activeTool === 'document_summary',
              }"
              :aria-label="t('canvas.ribbon.docGenerate')"
              @click="openDocGenerate('file')"
            >
              <FileText class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.docGenerate') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.ribbon.webGenerate')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.ribbon.webGenerate')"
              @click="openDocGenerate('web')"
            >
              <Link2 class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.webGenerate') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.ribbon.voiceSummary')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact }"
              :aria-label="t('canvas.ribbon.voiceSummary')"
              @click="openVoiceSummary"
            >
              <Mic class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.voiceSummary') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.mindMapSideToolbar.waterfall')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact, 'is-active': activeTool === 'waterfall' }"
              :aria-label="t('canvas.mindMapSideToolbar.waterfall')"
              @click="handleToolSelect('waterfall')"
            >
              <LayoutGrid class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.mindMapSideToolbar.waterfall') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.mindMapSideToolbar.oneSentence')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{
                'mm-btn--icon': props.compact,
                'is-active': activeTool === 'one_sentence',
              }"
              :aria-label="t('canvas.mindMapSideToolbar.oneSentence')"
              @click="ribbon.openSideTool('one_sentence')"
            >
              <MessageSquare class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.mindMapSideToolbar.oneSentence') }}</span
              >
            </button>
          </ElTooltip>
          <ElTooltip
            :content="t('canvas.floatingToolbar.aiSubgraph')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{ 'mm-btn--icon': props.compact, 'is-dimmed': !ribbon.hasSelection }"
              :aria-disabled="!ribbon.hasSelection"
              :aria-label="t('canvas.floatingToolbar.aiSubgraph')"
              @click="requireNodeSelection(() => ribbon.requestAiSubgraph())"
            >
              <GitBranch class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.floatingToolbar.aiSubgraph') }}</span
              >
            </button>
          </ElTooltip>
        </div>
      </template>

      <template v-if="ribbonTab === 'research'">
        <div class="mm-btn-group">
          <ElTooltip
            :content="t('canvas.ribbon.mindMate')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn"
              :class="{
                'mm-btn--icon': props.compact,
                'is-active': ribbon.isMindmateOpen,
              }"
              :aria-label="t('canvas.ribbon.mindMate')"
              @click="ribbon.toggleMindmate"
            >
              <Bot class="w-4 h-4" />
              <span
                v-if="!props.compact"
                class="mm-btn__label"
                >{{ t('canvas.ribbon.mindMate') }}</span
              >
            </button>
          </ElTooltip>
        </div>
      </template>
    </div>
    <button
      v-show="trackOverflowing"
      type="button"
      class="mm-toolbar__nudge mm-toolbar__nudge--right"
      :disabled="!canScrollRight"
      :aria-label="t('canvas.mindMapSlideOverlay.next')"
      @click="scrollTrack(1)"
    >
      <span
        class="mm-toolbar__nudge-tri"
        aria-hidden="true"
      />
    </button>
  </div>
</template>

<style src="./mindMapToolbarButtons.css"></style>
<style scoped src="./canvasToolbarMindMap.css"></style>
<style src="./canvasToolbarMindMapPopper.css"></style>
