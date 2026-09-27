<script setup lang="ts">
/**
 * Style, text, fill, and border controls for diagrams that do not use
 * mind-map themes. Same dropdowns as the former single-row toolbar.
 */
import { computed, ref } from 'vue'

import { Keyboard } from '@lucide/vue'

import CanvasMathInsertDialog from '@/components/canvas/CanvasMathInsertDialog.vue'
import CanvasToolbarBackgroundDropdown from '@/components/canvas/CanvasToolbarBackgroundDropdown.vue'
import CanvasToolbarBorderDropdown from '@/components/canvas/CanvasToolbarBorderDropdown.vue'
import CanvasToolbarStyleDropdown from '@/components/canvas/CanvasToolbarStyleDropdown.vue'
import CanvasToolbarTextDropdown from '@/components/canvas/CanvasToolbarTextDropdown.vue'
import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { toggleCanvasVirtualKeyboard } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { joinLabelAndMathSnippet } from '@/composables/core/markdownKatexDelimiter'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useUIStore } from '@/stores'
import { shouldReplaceLabelWithMathInsert } from '@/stores/diagram/diagramDefaultLabels'

const props = withDefaults(defineProps<{ compact?: boolean; keyboardOnly?: boolean }>(), {
  compact: false,
  keyboardOnly: false,
})

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramSession()
const uiStore = useUIStore()
const formatting = useCanvasToolbarFormatting()
const {
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
} = formatting
const backgroundOpacity = formatting.backgroundOpacity

const mathInsertDialogOpen = ref(false)
const insertEquationEnabled = computed(() => diagramStore.selectedNodes.length > 0)

function onBackgroundOpacityInput(value: number): void {
  backgroundOpacity.value = value
}

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
    const node = diagramStore.data?.nodes?.find((item) => item.id === nodeId)
    const base = String(node?.text ?? (node?.data as { label?: string } | undefined)?.label ?? '')
    const nextText =
      diagramStore.type && shouldReplaceLabelWithMathInsert(diagramStore.type, nodeId, base)
        ? snippet
        : joinLabelAndMathSnippet(base, snippet)
    eventBus.emit('node:text_updated', { nodeId, text: nextText })
  }
}
</script>

<template>
  <span class="inline-flex items-center shrink-0">
    <template v-if="!props.keyboardOnly">
      <CanvasToolbarStyleDropdown
        :compact="compact"
        :style-menu-label="t('canvas.toolbar.styleMenu')"
        :presets-label="t('canvas.toolbar.presetsLabel')"
        :wireframe-label="t('canvas.toolbar.wireframe')"
        :wireframe-mode="uiStore.wireframeMode"
        :style-presets="stylePresets"
        @apply-preset="handleApplyStylePreset"
        @toggle-wireframe="uiStore.toggleWireframe()"
      />
      <CanvasToolbarTextDropdown
        :compact="compact"
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
        :compact="compact"
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
        :compact="compact"
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
    </template>
    <I18nTooltip
      k="canvas.toolbar.moreAppVirtualKeyboard"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn mm-btn--icon"
        data-virtual-keyboard-chrome
        :aria-label="t('canvas.toolbar.moreAppVirtualKeyboard')"
        @click="toggleCanvasVirtualKeyboard"
      >
        <Keyboard class="w-4 h-4" />
        <span
          v-if="!compact"
          class="mm-btn__label"
        >
          <I18nText k="canvas.toolbar.moreAppVirtualKeyboard" />
        </span>
      </button>
    </I18nTooltip>
    <CanvasMathInsertDialog
      v-model="mathInsertDialogOpen"
      @confirm="handleMathInsertConfirm"
    />
  </span>
</template>
