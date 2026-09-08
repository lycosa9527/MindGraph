<script setup lang="ts">
/**
 * Home-tab format strip: painter, font, size, B/I, color, alignment.
 */
import { ElTooltip } from 'element-plus'

import { AlignCenter, AlignLeft, AlignRight, Bold, Italic, Paintbrush } from '@lucide/vue'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

const props = withDefaults(
  defineProps<{ compact?: boolean; hidePainter?: boolean; disabled?: boolean }>(),
  { compact: false, hidePainter: false, disabled: false }
)

const { t } = useLanguage()
const notify = useNotifications()
const {
  formatBrushActive,
  formatBrushLocked,
  fontFamily,
  fontSize,
  fontWeight,
  fontStyle,
  textAlign,
  textColor,
  handleToggleBold,
  handleToggleItalic,
  handleTextAlign,
  handleFontFamilyChange,
  handleFontSizeInput,
  handleTextColorPick,
  handleFormatBrush,
} = useCanvasToolbarFormatting()

function onNeedsSelectionClick(ev: MouseEvent): void {
  if (!props.disabled) return
  ev.preventDefault()
  ev.stopPropagation()
  notify.warning(t('canvas.toolbar.selectNodesFirst'))
}
</script>

<template>
  <div
    v-if="!hidePainter"
    class="mm-btn-group"
  >
    <ElTooltip
      :content="t('canvas.toolbar.formatPainter')"
      placement="bottom"
    >
      <button
        type="button"
        class="mm-btn mm-btn--icon"
        :class="{ 'is-active': formatBrushActive, 'is-locked': formatBrushLocked }"
        :aria-label="t('canvas.toolbar.formatPainter')"
        @click="() => handleFormatBrush()"
        @dblclick.prevent="handleFormatBrush({ lock: true })"
      >
        <Paintbrush class="w-4 h-4" />
      </button>
    </ElTooltip>
  </div>
  <span
    v-if="!hidePainter"
    class="mm-sep"
  />
  <div
    class="mm-style-cluster"
    :class="{ 'is-dimmed': disabled }"
    :aria-disabled="disabled"
    @click="onNeedsSelectionClick"
  >
    <span
      v-if="hidePainter && !compact"
      class="mm-style-kicker"
      >{{ t('canvas.v3.textStyle') }}</span
    >
    <select
      class="mm-select"
      :value="fontFamily"
      :aria-label="t('canvas.v3.fontFamily')"
      @change="handleFontFamilyChange"
    >
      <option :value="DIAGRAM_NODE_FONT_STACK">
        {{ t('canvas.floatingToolbar.fontDefault') }}
      </option>
      <option value="Inter">Inter</option>
      <option value="Microsoft YaHei">微软雅黑</option>
      <option value="Arial">Arial</option>
      <option value="SimSun">{{ t('canvas.floatingToolbar.fontSimSun') }}</option>
    </select>
    <input
      class="mm-input-size"
      type="number"
      min="8"
      max="72"
      :value="fontSize"
      :aria-label="t('canvas.v3.fontSize')"
      @change="handleFontSizeInput"
    />
    <span class="mm-sep" />
    <div class="mm-btn-group">
      <ElTooltip
        content="B"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn mm-btn--icon"
          :class="{ 'is-active': fontWeight === 'bold' }"
          aria-label="Bold"
          @click="handleToggleBold"
        >
          <Bold class="w-4 h-4" />
        </button>
      </ElTooltip>
      <ElTooltip
        content="I"
        placement="bottom"
      >
        <button
          type="button"
          class="mm-btn mm-btn--icon"
          :class="{ 'is-active': fontStyle === 'italic' }"
          aria-label="Italic"
          @click="handleToggleItalic"
        >
          <Italic class="w-4 h-4" />
        </button>
      </ElTooltip>
      <label
        class="mm-color"
        :title="t('canvas.v3.colorText')"
      >
        <span class="mm-color__glyph">A</span>
        <input
          class="mm-color__input"
          type="color"
          :value="textColor"
          @input="handleTextColorPick(($event.target as HTMLInputElement).value)"
        />
      </label>
    </div>
    <span class="mm-sep" />
    <div class="mm-btn-group">
      <button
        type="button"
        class="mm-btn mm-btn--icon"
        :class="{ 'is-active': textAlign === 'left' }"
        :aria-label="t('canvas.v3.ribbon.alignLeft')"
        @click="handleTextAlign('left')"
      >
        <AlignLeft class="w-4 h-4" />
      </button>
      <button
        type="button"
        class="mm-btn mm-btn--icon"
        :class="{ 'is-active': textAlign === 'center' }"
        :aria-label="t('canvas.v3.ribbon.alignCenter')"
        @click="handleTextAlign('center')"
      >
        <AlignCenter class="w-4 h-4" />
      </button>
      <button
        type="button"
        class="mm-btn mm-btn--icon"
        :class="{ 'is-active': textAlign === 'right' }"
        :aria-label="t('canvas.v3.ribbon.alignRight')"
        @click="handleTextAlign('right')"
      >
        <AlignRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>
