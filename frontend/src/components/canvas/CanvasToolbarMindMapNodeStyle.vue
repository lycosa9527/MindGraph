<script setup lang="ts">
/**
 * Style-tab node chrome — same 28px row metrics as the text-style strip.
 */
import { ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElPopover, ElTooltip } from 'element-plus'

import { ChevronDown, Minus, Square } from '@lucide/vue'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { FLOATING_TOOLBAR_COLORS } from '@/config/floatingToolbarColors'
import { NODE_SHAPE_OPTIONS, type NodeShape } from '@/utils/nodeShapeStyle'

const props = withDefaults(defineProps<{ compact?: boolean; disabled?: boolean }>(), {
  compact: false,
  disabled: false,
})

const { t } = useLanguage()
const notify = useNotifications()
const {
  backgroundColor,
  borderColor,
  nodeShape,
  handleFillColorPick,
  handleBorderColorPick,
  handleNodeShapePick,
} = useCanvasToolbarFormatting()

const fillOpen = ref(false)
const borderOpen = ref(false)

const shapeLabels: Record<NodeShape, string> = {
  rounded: 'canvas.floatingToolbar.shapeRounded',
  rectangle: 'canvas.floatingToolbar.shapeRectangle',
  oval: 'canvas.floatingToolbar.shapeOval',
  underline: 'canvas.floatingToolbar.shapeUnderline',
}

function pickColor(panel: 'fill' | 'border', color: string): void {
  if (panel === 'fill') {
    handleFillColorPick(color)
    fillOpen.value = false
  } else {
    handleBorderColorPick(color)
    borderOpen.value = false
  }
}

function onCustomColor(panel: 'fill' | 'border', ev: Event): void {
  pickColor(panel, (ev.target as HTMLInputElement).value)
}

function onNeedsSelectionClick(ev: MouseEvent): void {
  if (!props.disabled) return
  ev.preventDefault()
  ev.stopPropagation()
  notify.warning(t('canvas.toolbar.selectNodesFirst'))
}
</script>

<template>
  <div
    class="mm-style-cluster"
    :class="{ 'is-dimmed': disabled }"
    :aria-disabled="disabled"
    @click="onNeedsSelectionClick"
  >
    <span
      v-if="!compact"
      class="mm-style-kicker"
      >{{ t('canvas.v3.ribbon.nodeStyle') }}</span
    >
    <ElDropdown
      trigger="click"
      placement="bottom-start"
      popper-class="node-floating-toolbar-popper"
    >
      <button
        type="button"
        class="nft-btn nft-btn--shape"
        :title="t('canvas.floatingToolbar.shapeLabel')"
      >
        <Square
          v-if="nodeShape === 'rectangle' || nodeShape === 'rounded'"
          class="nft-icon"
          :stroke-width="1.5"
        />
        <span
          v-else-if="nodeShape === 'oval'"
          class="nft-shape-oval"
        />
        <Minus
          v-else
          class="nft-icon"
          :stroke-width="2.5"
        />
        <ChevronDown class="nft-chevron" />
      </button>
      <template #dropdown>
        <ElDropdownMenu class="nft-dropdown-menu">
          <ElDropdownItem
            v-for="shape in NODE_SHAPE_OPTIONS"
            :key="shape"
            class="nft-dropdown-item"
            :class="{ 'nft-dropdown-item--active': nodeShape === shape }"
            @click="handleNodeShapePick(shape)"
          >
            {{ t(shapeLabels[shape]) }}
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>

    <ElPopover
      v-model:visible="borderOpen"
      trigger="click"
      placement="bottom"
      :width="176"
      popper-class="node-floating-toolbar-popper"
    >
      <template #reference>
        <span class="nft-color-ref">
          <ElTooltip
            :content="t('canvas.floatingToolbar.borderColor')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn mm-btn--icon"
              :aria-label="t('canvas.floatingToolbar.borderColor')"
            >
              <span
                class="mm-swatch mm-swatch--ring"
                :style="{ borderColor: borderColor }"
              />
            </button>
          </ElTooltip>
        </span>
      </template>
      <div class="nft-color-grid">
        <button
          v-for="color in FLOATING_TOOLBAR_COLORS"
          :key="'border-' + color"
          type="button"
          class="nft-palette-swatch"
          :style="{ backgroundColor: color }"
          @click="pickColor('border', color)"
        />
      </div>
      <input
        type="color"
        class="nft-native-color"
        :value="borderColor"
        @input="onCustomColor('border', $event)"
      />
    </ElPopover>

    <ElPopover
      v-model:visible="fillOpen"
      trigger="click"
      placement="bottom"
      :width="176"
      popper-class="node-floating-toolbar-popper"
    >
      <template #reference>
        <span class="nft-color-ref">
          <ElTooltip
            :content="t('canvas.floatingToolbar.fillColor')"
            placement="bottom"
          >
            <button
              type="button"
              class="mm-btn mm-btn--icon"
              :aria-label="t('canvas.floatingToolbar.fillColor')"
            >
              <span
                class="mm-swatch mm-swatch--fill"
                :style="{ backgroundColor: backgroundColor }"
              />
            </button>
          </ElTooltip>
        </span>
      </template>
      <div class="nft-color-grid">
        <button
          v-for="color in FLOATING_TOOLBAR_COLORS"
          :key="'fill-' + color"
          type="button"
          class="nft-palette-swatch"
          :style="{ backgroundColor: color }"
          @click="pickColor('fill', color)"
        />
      </div>
      <input
        type="color"
        class="nft-native-color"
        :value="backgroundColor"
        @input="onCustomColor('fill', $event)"
      />
    </ElPopover>
  </div>
</template>

<style src="./canvasToolbarMindMapNft.css"></style>
