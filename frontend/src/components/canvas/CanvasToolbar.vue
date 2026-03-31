<script setup lang="ts">
/**
 * CanvasToolbar - Floating toolbar for canvas editing
 */
import { computed, ref } from 'vue'

import { ElButton, ElTooltip } from 'element-plus'

import { ArrowDownUp, Brush } from 'lucide-vue-next'

import { useCanvasToolbarApps, useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { joinLabelAndMathSnippet } from '@/composables/core/markdownKatexDelimiter'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { useDiagramStore, useUIStore } from '@/stores'
import { shouldReplaceLabelWithMathInsert } from '@/stores/diagram/diagramDefaultLabels'

import CanvasMathInsertDialog from './CanvasMathInsertDialog.vue'
import CanvasToolbarAddDelete from './CanvasToolbarAddDelete.vue'
import CanvasToolbarAiSection from './CanvasToolbarAiSection.vue'
import CanvasToolbarBackgroundDropdown from './CanvasToolbarBackgroundDropdown.vue'
import CanvasToolbarBorderDropdown from './CanvasToolbarBorderDropdown.vue'
import CanvasToolbarMoreAppsDropdown from './CanvasToolbarMoreAppsDropdown.vue'
import CanvasToolbarStyleDropdown from './CanvasToolbarStyleDropdown.vue'
import CanvasToolbarTextDropdown from './CanvasToolbarTextDropdown.vue'
import CanvasToolbarUndoRedo from './CanvasToolbarUndoRedo.vue'

/** When true, flatter styles for use inside CanvasTopBar (single merged chrome row). */
const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })

const { t } = useLanguage()
const notify = useNotifications()

const diagramStore = useDiagramStore()
const uiStore = useUIStore()

const { handleAddNode, handleDeleteNode, handleAddCause, handleAddEffect } = useNodeActions({
  addNodePrimaryBehavior: 'toolbarPrimary',
  includeTreeMapPrimaryAdd: false,
  includeMultiFlowPrimaryAdd: false,
})

const formatting = useCanvasToolbarFormatting()
const {
  formatBrushActive,
  stylePresets,
  fontFamily,
  fontSize,
  textColor,
  fontWeight,
  fontStyle,
  textDecoration,
  textAlign,
  textColorPalette,
  backgroundColors,
  borderColor,
  borderColorPalette,
  borderWidth,
  borderStyle,
  borderStyleOptions,
  getBorderPreviewStyle,
  handleApplyStylePreset,
  applyBackgroundToSelected,
  applyBorderToSelected,
  handleToggleBold,
  handleToggleItalic,
  handleToggleUnderline,
  handleToggleStrikethrough,
  handleTextAlign,
  handleFontFamilyChange,
  handleFontSizeInput,
  handleTextColorPick,
  handleFormatBrush,
} = formatting
const backgroundOpacity = formatting.backgroundOpacity

function onBackgroundOpacityInput(v: number) {
  backgroundOpacity.value = v
}

const {
  aiBlockedByCollab,
  isAIGenerating,
  isConceptMap,
  moreApps,
  handleAIGenerate,
  handleConceptGeneration,
  handleMoreAppItem,
} = useCanvasToolbarApps()

const isMultiFlowMap = computed(() => diagramStore.type === 'multi_flow_map')
const isBridgeMap = computed(() => diagramStore.type === 'bridge_map')
const isFlowMap = computed(() => diagramStore.type === 'flow_map')

const mathInsertDialogOpen = ref(false)

const insertEquationEnabled = computed(() => diagramStore.selectedNodes.length > 0)

function handleOpenMathInsert(): void {
  if (diagramStore.selectedNodes.length === 0) {
    notify.warning(t('canvas.toolbar.insertEquationSelectNode'))
    return
  }
  mathInsertDialogOpen.value = true
}

function handleMathInsertConfirm(latex: string): void {
  const trimmed = latex.trim()
  if (!trimmed) return
  const nodeId = diagramStore.selectedNodes[0]
  if (!nodeId) return
  const snippet = `$${trimmed}$`
  let consumed = false
  const unsub = eventBus.on('node_editor:insert_text_consumed', ({ nodeId: id }) => {
    if (id === nodeId) consumed = true
  })
  eventBus.emit('node_editor:insert_text', { nodeId, snippet })
  unsub()
  if (!consumed) {
    const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
    const base = String(node?.text ?? (node?.data as { label?: string } | undefined)?.label ?? '')
    const nextText =
      diagramStore.type && shouldReplaceLabelWithMathInsert(diagramStore.type, nodeId, base)
        ? snippet
        : joinLabelAndMathSnippet(base, snippet)
    eventBus.emit('node:text_updated', { nodeId, text: nextText })
  }
}

function handleUndo() {
  diagramStore.undo()
}

function handleRedo() {
  diagramStore.redo()
}

function handleToggleOrientation() {
  diagramStore.toggleFlowMapOrientation()
  notify.success(t('canvas.toolbar.layoutDirectionToggled'))
}
</script>

<template>
  <div
    class="canvas-toolbar relative z-10 w-full flex justify-center"
    :class="props.embedded ? 'max-w-none' : 'max-w-[min(100vw-1rem,1200px)]'"
  >
    <div
      class="flex items-center justify-center w-full overflow-x-auto"
      :class="
        props.embedded
          ? 'rounded-lg p-1 bg-transparent'
          : 'rounded-xl shadow-lg p-1.5 border border-gray-200/80 dark:border-gray-600/80 bg-white/90 dark:bg-gray-800/90 backdrop-blur-md'
      "
    >
      <div
        class="toolbar-content flex items-center bg-gray-50 dark:bg-gray-700/50 rounded-lg p-1 gap-0.5 min-w-min"
      >
        <CanvasToolbarUndoRedo
          :can-undo="diagramStore.canUndo"
          :can-redo="diagramStore.canRedo"
          :undo-label="t('canvas.toolbar.undo')"
          :redo-label="t('canvas.toolbar.redo')"
          @undo="handleUndo"
          @redo="handleRedo"
        />

        <div class="divider" />

        <CanvasToolbarAddDelete
          :is-multi-flow-map="isMultiFlowMap"
          :is-bridge-map="isBridgeMap"
          :add-cause-label="t('canvas.toolbar.addCause')"
          :add-effect-label="t('canvas.toolbar.addEffect')"
          :add-analogy-pair-label="t('canvas.toolbar.addAnalogyPair')"
          :add-pair-short="t('canvas.toolbar.addPairShort')"
          :add-node-label="t('canvas.toolbar.addNode')"
          :add-short="t('canvas.toolbar.addShort')"
          :delete-node-label="t('canvas.toolbar.deleteNode')"
          :delete-short="t('canvas.toolbar.deleteShort')"
          @add-cause="handleAddCause"
          @add-effect="handleAddEffect"
          @add-node="handleAddNode"
          @delete-node="handleDeleteNode"
        />

        <div class="divider" />

        <ElTooltip
          :content="t('canvas.toolbar.formatPainter')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            :class="formatBrushActive ? 'bg-purple-100 ring-1 ring-purple-400 rounded' : ''"
            @click="handleFormatBrush"
          >
            <Brush
              class="w-4 h-4"
              :class="formatBrushActive ? 'text-purple-600' : 'text-purple-500'"
            />
          </ElButton>
        </ElTooltip>

        <ElTooltip
          v-if="isFlowMap"
          :content="t('canvas.toolbar.toggleDirection')"
          placement="bottom"
        >
          <ElButton
            text
            size="small"
            @click="handleToggleOrientation"
          >
            <ArrowDownUp class="w-4 h-4 text-blue-500" />
            <span>{{ t('canvas.toolbar.directionLabel') }}</span>
          </ElButton>
        </ElTooltip>

        <div class="divider" />

        <CanvasToolbarStyleDropdown
          :style-menu-label="t('canvas.toolbar.styleMenu')"
          :presets-label="t('canvas.toolbar.presetsLabel')"
          :wireframe-label="t('canvas.toolbar.wireframe')"
          :wireframe-mode="uiStore.wireframeMode"
          :style-presets="stylePresets"
          @apply-preset="handleApplyStylePreset"
          @toggle-wireframe="uiStore.toggleWireframe()"
        />

        <CanvasToolbarTextDropdown
          :text-style-menu-label="t('canvas.toolbar.textStyleMenu')"
          :format-label="t('canvas.toolbar.formatLabel')"
          :align-label="t('canvas.toolbar.alignLabel')"
          :font-label="t('canvas.toolbar.fontLabel')"
          :font-group-chinese="t('canvas.toolbar.fontGroupChinese')"
          :font-group-english="t('canvas.toolbar.fontGroupEnglish')"
          :color-label="t('canvas.toolbar.colorLabel')"
          :insert-equation-label="t('canvas.toolbar.insertEquation')"
          :insert-equation-tooltip="t('canvas.toolbar.insertEquationTooltip')"
          :insert-equation-enabled="insertEquationEnabled"
          :font-family="fontFamily"
          :font-size="fontSize"
          :font-weight="fontWeight"
          :font-style="fontStyle"
          :text-decoration="textDecoration"
          :text-align="textAlign"
          :text-color="textColor"
          :text-color-palette="textColorPalette"
          @toggle-bold="handleToggleBold"
          @toggle-italic="handleToggleItalic"
          @toggle-underline="handleToggleUnderline"
          @toggle-strikethrough="handleToggleStrikethrough"
          @set-text-align="handleTextAlign"
          @font-family-change="handleFontFamilyChange"
          @font-size-input="handleFontSizeInput"
          @text-color-pick="handleTextColorPick"
          @open-math-insert="handleOpenMathInsert"
        />

        <CanvasToolbarBackgroundDropdown
          :bg-menu-label="t('canvas.toolbar.bgMenu')"
          :bg-color-label="t('canvas.toolbar.bgColorLabel')"
          :opacity-label="t('canvas.toolbar.opacityLabel')"
          :background-colors="backgroundColors"
          :background-opacity="backgroundOpacity"
          @pick-color="applyBackgroundToSelected"
          @update:background-opacity="onBackgroundOpacityInput"
          @apply-background="applyBackgroundToSelected()"
        />

        <CanvasToolbarBorderDropdown
          :border-menu-label="t('canvas.toolbar.borderMenu')"
          :color-label="t('canvas.toolbar.colorLabel')"
          :border-width-label="t('canvas.toolbar.borderWidthLabel')"
          :border-style-label="t('canvas.toolbar.borderStyleLabel')"
          :border-color-palette="borderColorPalette"
          :border-color="borderColor"
          :border-width="borderWidth"
          :border-style="borderStyle"
          :border-style-options="borderStyleOptions"
          :get-border-preview-style="getBorderPreviewStyle"
          @apply-border="applyBorderToSelected"
        />

        <CanvasToolbarAiSection
          :is-concept-map="isConceptMap"
          :is-a-i-generating="isAIGenerating"
          :ai-blocked-by-collab="aiBlockedByCollab"
          :concept-generation-label="t('canvas.toolbar.conceptGeneration')"
          :ai-generate-label="t('canvas.toolbar.aiGenerate')"
          :ai-generating-label="t('canvas.toolbar.aiGenerating')"
          @concept-generation="handleConceptGeneration"
          @ai-generate="handleAIGenerate"
        />

        <div class="divider" />

        <CanvasToolbarMoreAppsDropdown
          :more-apps-label="t('canvas.toolbar.moreApps')"
          :apps="moreApps"
          @select-app="handleMoreAppItem"
        />
      </div>
    </div>

    <CanvasMathInsertDialog
      v-model="mathInsertDialogOpen"
      @confirm="handleMathInsertConfirm"
    />
  </div>
</template>

<style scoped>
:deep(.divider) {
  height: 20px;
  width: 1px;
  background-color: #d1d5db;
  margin: 0 6px;
}

.toolbar-content {
  flex-wrap: nowrap;
  white-space: nowrap;
}

:deep(.toolbar-content .el-button) {
  --el-button-hover-bg-color: transparent;
  --el-button-hover-text-color: inherit;
  padding: 8px !important;
  margin: 0 !important;
  min-height: auto !important;
  height: auto !important;
  border-radius: 4px !important;
  transition: all 0.15s ease !important;
  border: none !important;
  font-size: 12px !important;
}

:deep(.toolbar-content .el-button--text) {
  color: #4b5563 !important;
  background: transparent !important;
}

:deep(.toolbar-content .el-button--text:hover) {
  background-color: #d1d5db !important;
  color: #374151 !important;
}

:deep(.toolbar-content .el-button--text:active) {
  background-color: #9ca3af !important;
}

:deep(.toolbar-content .el-button--text span) {
  margin-left: 0 !important;
}

:deep(.toolbar-content .el-button--text:not(:has(span))) {
  padding: 8px !important;
}

:deep(.toolbar-content .el-button:has(span)) {
  display: inline-flex !important;
  align-items: center !important;
  gap: 4px !important;
}

:deep(.dark .toolbar-content .el-button--text) {
  color: #d1d5db !important;
}

:deep(.dark .toolbar-content .el-button--text:hover) {
  background-color: #4b5563 !important;
  color: #f3f4f6 !important;
}

:deep(.dark .toolbar-content .el-button--text:active) {
  background-color: #374151 !important;
}

:deep(.ai-btn) {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border: none !important;
  padding: 6px 16px !important;
  margin-left: 8px !important;
  gap: 6px !important;
  box-sizing: border-box !important;
}

:deep(.ai-btn:hover) {
  background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

:deep(.ai-btn span) {
  color: white !important;
}

@property --ai-toolbar-ring-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

:deep(.ai-btn--generating) {
  position: relative !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 2px !important;
}

:deep(.ai-btn--generating:hover) {
  transform: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.ai-btn--generating::before) {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 6px;
  padding: 2px;
  --ai-toolbar-ring-angle: 0deg;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: ai-toolbar-ring-spin 2.5s linear infinite;
  background: conic-gradient(
    from var(--ai-toolbar-ring-angle) at 50% 50%,
    rgba(59, 130, 246, 0.35) 0deg,
    rgba(255, 255, 255, 0.75) 52deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 228deg,
    rgba(255, 255, 255, 0.75) 308deg,
    rgba(59, 130, 246, 0.35) 360deg
  );
}

:deep(.ai-btn--generating .el-button__inner),
:deep(.ai-btn--generating > span) {
  position: relative;
  z-index: 1;
  box-sizing: border-box !important;
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
  border-radius: 4px !important;
  padding: 4px 14px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 6px !important;
}

:deep(.dark .ai-btn--generating::before) {
  background: conic-gradient(
    from var(--ai-toolbar-ring-angle) at 50% 50%,
    rgba(59, 130, 246, 0.4) 0deg,
    rgba(31, 41, 55, 0.92) 52deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 228deg,
    rgba(31, 41, 55, 0.92) 308deg,
    rgba(59, 130, 246, 0.4) 360deg
  );
}

@keyframes ai-toolbar-ring-spin {
  to {
    --ai-toolbar-ring-angle: 360deg;
  }
}

:deep(.more-apps-btn) {
  background: white !important;
  border: 1px solid #e5e7eb !important;
  color: #374151 !important;
  padding: 6px 12px !important;
  margin-left: 12px !important;
  gap: 4px !important;
}

:deep(.more-apps-btn:hover) {
  background: #f9fafb !important;
  border-color: #d1d5db !important;
}

:deep(.more-apps-btn span) {
  color: #374151 !important;
}

:deep(.more-apps-menu) {
  width: 280px !important;
}

:deep(.more-apps-menu .el-dropdown-menu__item) {
  padding: 8px 12px !important;
  line-height: 1.4 !important;
}

:deep(.dark .divider) {
  background-color: #4b5563;
}

:deep(.dark .more-apps-btn) {
  background: #374151 !important;
  border-color: #4b5563 !important;
  color: #e5e7eb !important;
}
</style>
