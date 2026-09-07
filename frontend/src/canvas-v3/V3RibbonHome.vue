<script setup lang="ts">
import { h, ref } from 'vue'

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  ClipboardPaste,
  Copy,
  Eraser,
  FunctionSquare,
  Italic,
  Keyboard,
  Paintbrush,
  Palette,
  RotateCcw,
  Scissors,
  Settings2,
  Strikethrough,
  Trash2,
  Underline,
} from '@lucide/vue'

import CanvasMathInsertDialog from '@/components/canvas/CanvasMathInsertDialog.vue'
import MindMapInsertNodeIcon from '@/components/canvas/MindMapInsertNodeIcon.vue'
import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { joinLabelAndMathSnippet } from '@/composables/core/markdownKatexDelimiter'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramStore } from '@/stores'
import { shouldReplaceLabelWithMathInsert } from '@/stores/diagram/diagramDefaultLabels'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { NODE_SHAPE_OPTIONS } from '@/utils/nodeShapeStyle'

import V3RibbonCommand from './V3RibbonCommand.vue'
import V3RibbonGroup from './V3RibbonGroup.vue'
import { useV3RibbonActions } from './useV3RibbonActions'

withDefaults(
  defineProps<{
    classic?: boolean
    disabled?: boolean
  }>(),
  { classic: false, disabled: false }
)

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const AddChildNodeIcon = () => h(MindMapInsertNodeIcon, { kind: 'child' })
const AddSiblingNodeIcon = () => h(MindMapInsertNodeIcon, { kind: 'sibling' })
const actions = useV3RibbonActions()
const {
  formatBrushActive,
  fontFamily,
  fontSize,
  fontWeight,
  fontStyle,
  textDecoration,
  textAlign,
  textColor,
  backgroundColor,
  borderColor,
  nodeShape,
  handleToggleBold,
  handleToggleItalic,
  handleToggleUnderline,
  handleToggleStrikethrough,
  handleTextAlign,
  handleFontFamilyChange,
  handleFontSizeInput,
  handleTextColorPick,
  handleFillColorPick,
  handleBorderColorPick,
  handleNodeShapePick,
  handleFormatBrush,
} = useCanvasToolbarFormatting()
const mathOpen = ref(false)

function openMath(): void {
  if (diagramStore.selectedNodes.length === 0) {
    notify.warning(t('canvas.toolbar.insertEquationSelectNode'))
    return
  }
  mathOpen.value = true
}

function onMathConfirm(latex: string): void {
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
    const node = diagramStore.data?.nodes?.find((item) => item.id === nodeId)
    const base = String(node?.text ?? (node?.data as { label?: string } | undefined)?.label ?? '')
    const nextText =
      diagramStore.type && shouldReplaceLabelWithMathInsert(diagramStore.type, nodeId, base)
        ? snippet
        : joinLabelAndMathSnippet(base, snippet)
    eventBus.emit('node:text_updated', { nodeId, text: nextText })
  }
}

function onFontFamily(event: Event): void {
  handleFontFamilyChange(event)
}

function onFontSize(event: Event): void {
  handleFontSizeInput(event)
}

function focusProperty(): void {
  eventBus.emit('panel:open_requested', { panel: 'property', source: 'v3-ribbon' })
}
</script>

<template>
  <V3RibbonGroup
    group="clipboard"
    :label="t('canvas.v3.ribbon.groupClipboard')"
    :classic="classic"
  >
    <template #lead>
      <V3RibbonCommand
        :label="t('diagram.contextMenu.paste')"
        :icon="ClipboardPaste"
        variant="stacked"
        primary
        :disabled="disabled || !actions.canPaste"
        @click="actions.pasteAtSelection"
      />
    </template>
    <div class="v3-ribbon-group__stack">
      <V3RibbonCommand
        :label="t('diagram.contextMenu.cut')"
        :icon="Scissors"
        variant="icon"
        :disabled="disabled"
        @click="actions.cutSelected"
      />
      <V3RibbonCommand
        :label="t('diagram.contextMenu.copy')"
        :icon="Copy"
        variant="icon"
        :disabled="disabled"
        @click="actions.copySelected"
      />
      <V3RibbonCommand
        v-if="classic"
        :label="t('canvas.toolbar.formatPainter')"
        :icon="Paintbrush"
        variant="icon"
        :active="formatBrushActive"
        :disabled="disabled"
        @click="handleFormatBrush"
        @dblclick="handleFormatBrush({ lock: true })"
      />
    </div>
  </V3RibbonGroup>
  <V3RibbonGroup
    group="font"
    :label="t('canvas.v3.ribbon.groupFont')"
    :classic="classic"
  >
    <div class="v3-ribbon-group__line">
      <select
        v-if="classic"
        class="v3-ribbon-select"
        :value="fontFamily"
        :disabled="disabled"
        @change="onFontFamily"
      >
        <option :value="DIAGRAM_NODE_FONT_STACK">
          {{ t('canvas.floatingToolbar.fontDefault') }}
        </option>
        <option value="Inter">Inter</option>
        <option value="Arial">Arial</option>
        <option value="SimSun">{{ t('canvas.floatingToolbar.fontSimSun') }}</option>
      </select>
      <input
        v-if="classic"
        class="v3-ribbon-input"
        type="number"
        min="8"
        max="72"
        :value="fontSize"
        :disabled="disabled"
        @change="onFontSize"
      />
      <V3RibbonCommand
        label="B"
        :icon="Bold"
        variant="icon"
        :active="fontWeight === 'bold'"
        :disabled="disabled"
        @click="handleToggleBold"
      />
      <V3RibbonCommand
        label="I"
        :icon="Italic"
        variant="icon"
        :active="fontStyle === 'italic'"
        :disabled="disabled"
        @click="handleToggleItalic"
      />
      <V3RibbonCommand
        label="U"
        :icon="Underline"
        variant="icon"
        :active="String(textDecoration).includes('underline')"
        :disabled="disabled"
        @click="handleToggleUnderline"
      />
      <V3RibbonCommand
        v-if="classic"
        label="S"
        :icon="Strikethrough"
        variant="icon"
        :active="String(textDecoration).includes('line-through')"
        :disabled="disabled"
        @click="handleToggleStrikethrough"
      />
    </div>
    <div
      v-if="classic"
      class="v3-ribbon-group__line"
    >
      <input
        type="color"
        class="v3-ribbon-input"
        :value="textColor"
        :disabled="disabled"
        :title="t('canvas.v3.colorText')"
        @change="handleTextColorPick(($event.target as HTMLInputElement).value)"
      />
      <V3RibbonCommand
        :label="t('panel.properties')"
        :icon="Settings2"
        variant="icon"
        :disabled="disabled"
        @click="focusProperty"
      />
    </div>
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="paragraph"
    :label="t('canvas.v3.ribbon.groupParagraph')"
    :classic="classic"
  >
    <div class="v3-ribbon-group__line">
      <V3RibbonCommand
        :label="t('canvas.v3.ribbon.alignLeft')"
        :icon="AlignLeft"
        variant="icon"
        :active="textAlign === 'left'"
        :disabled="disabled"
        @click="handleTextAlign('left')"
      />
      <V3RibbonCommand
        :label="t('canvas.v3.ribbon.alignCenter')"
        :icon="AlignCenter"
        variant="icon"
        :active="textAlign === 'center'"
        :disabled="disabled"
        @click="handleTextAlign('center')"
      />
      <V3RibbonCommand
        :label="t('canvas.v3.ribbon.alignRight')"
        :icon="AlignRight"
        variant="icon"
        :active="textAlign === 'right'"
        :disabled="disabled"
        @click="handleTextAlign('right')"
      />
    </div>
    <div class="v3-ribbon-group__line">
      <input
        type="color"
        class="v3-ribbon-input"
        :value="backgroundColor"
        :disabled="disabled"
        :title="t('canvas.v3.colorFill')"
        @change="handleFillColorPick(($event.target as HTMLInputElement).value)"
      />
      <input
        type="color"
        class="v3-ribbon-input"
        :value="borderColor"
        :disabled="disabled"
        :title="t('canvas.v3.colorStroke')"
        @change="handleBorderColorPick(($event.target as HTMLInputElement).value)"
      />
      <select
        class="v3-ribbon-select"
        :value="nodeShape"
        :disabled="disabled"
        @change="
          handleNodeShapePick(
            ($event.target as HTMLSelectElement).value as (typeof NODE_SHAPE_OPTIONS)[number]
          )
        "
      >
        <option
          v-for="shape in NODE_SHAPE_OPTIONS"
          :key="shape"
          :value="shape"
        >
          {{ t(`canvas.floatingToolbar.shape${shape.charAt(0).toUpperCase()}${shape.slice(1)}`) }}
        </option>
      </select>
    </div>
  </V3RibbonGroup>
  <V3RibbonGroup
    group="nodes"
    :label="t('canvas.v3.ribbon.groupNodes')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.addChildNode')"
      :icon="AddChildNodeIcon"
      variant="stacked"
      :disabled="disabled"
      @click="actions.handleAddChildClick"
    />
    <V3RibbonCommand
      :label="t('canvas.toolbar.addSiblingNode')"
      :icon="AddSiblingNodeIcon"
      variant="stacked"
      :disabled="disabled"
      @click="actions.handleAddSibling"
    />
    <V3RibbonCommand
      :label="t('canvas.toolbar.deleteShort')"
      :icon="Trash2"
      variant="stacked"
      :disabled="disabled"
      @click="actions.handleDeleteNode"
    />
    <V3RibbonCommand
      v-if="classic"
      :label="t('canvas.v3.empty')"
      :icon="Eraser"
      variant="stacked"
      :disabled="disabled"
      @click="actions.emptySelected"
    />
    <V3RibbonCommand
      :label="t('canvas.v3.palette')"
      :icon="Palette"
      variant="stacked"
      :active="actions.isNodePaletteOpen"
      :disabled="disabled"
      @click="actions.openNodePalette"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="insert"
    :label="t('canvas.v3.ribbon.groupInsert')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.toolbar.insertEquation')"
      :icon="FunctionSquare"
      variant="stacked"
      :disabled="disabled"
      @click="openMath"
    />
    <V3RibbonCommand
      :label="t('canvas.toolbar.moreAppVirtualKeyboard')"
      :icon="Keyboard"
      variant="stacked"
      :disabled="disabled"
      @click="actions.toggleVirtualKeyboard"
    />
  </V3RibbonGroup>
  <V3RibbonGroup
    v-if="classic"
    group="editing"
    :label="t('canvas.v3.ribbon.groupEditing')"
    :classic="classic"
  >
    <V3RibbonCommand
      :label="t('canvas.v3.resetStyles')"
      :icon="RotateCcw"
      variant="stacked"
      :disabled="disabled"
      @click="actions.resetNodeStyles"
    />
  </V3RibbonGroup>
  <CanvasMathInsertDialog
    v-model="mathOpen"
    @confirm="onMathConfirm"
  />
</template>
