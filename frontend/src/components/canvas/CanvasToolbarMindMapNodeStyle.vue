<script setup lang="ts">
/**
 * Style-tab node chrome — same 28px row metrics as the text-style strip.
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElPopover } from 'element-plus'

import { ChevronDown, Minus, Square } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import I18nTooltip from '@/components/common/I18nTooltip.vue'
import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { type NodeShape, nodeShapeOptionsForDiagram } from '@/utils/nodeShapeStyle'

import FloatingToolbarColorPicker from './FloatingToolbarColorPicker.vue'

const props = withDefaults(defineProps<{ compact?: boolean; disabled?: boolean }>(), {
  compact: false,
  disabled: false,
})

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramSession()
const {
  backgroundColor,
  nativeFillColor,
  borderColor,
  nativeBorderColor,
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

const shapeOptions = computed(() => nodeShapeOptionsForDiagram(diagramStore.type))

/** Dimension labels: hide shape / fill / border — text styling lives on the format strip. */
const selectedIsTextOnlyLabel = computed(() => {
  const ids = diagramStore.selectedNodes
  if (ids.length !== 1) return false
  const node = diagramStore.data?.nodes?.find((item) => item.id === ids[0])
  return node?.type === 'label'
})
const hideNodeShape = computed(() => {
  const ids = diagramStore.selectedNodes
  if (ids.length !== 1) return false
  const node = diagramStore.data?.nodes?.find((item) => item.id === ids[0])
  return node?.type === 'boundary' || node?.type === 'label'
})
const hideNodeFillAndBorder = computed(() => selectedIsTextOnlyLabel.value)
const showNodeStyleChrome = computed(() => !hideNodeShape.value || !hideNodeFillAndBorder.value)

function pickColor(panel: 'fill' | 'border', color: string): void {
  if (panel === 'fill') {
    handleFillColorPick(color)
    fillOpen.value = false
  } else {
    handleBorderColorPick(color)
    borderOpen.value = false
  }
}

function onNeedsSelectionClick(ev: MouseEvent): void {
  if (!props.disabled) return
  ev.preventDefault()
  ev.stopPropagation()
  notify.warningKey('canvas.toolbar.selectNodesFirst')
}
</script>

<template>
  <div
    v-if="showNodeStyleChrome"
    class="mm-style-cluster"
    :class="{ 'is-dimmed': disabled }"
    :aria-disabled="disabled"
    @click="onNeedsSelectionClick"
  >
    <span
      v-if="!compact"
      class="mm-style-kicker"
    >
      <I18nText k="canvas.ribbon.nodeStyle" />
    </span>
    <ElDropdown
      v-if="!hideNodeShape"
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
          v-if="nodeShape == null || nodeShape === 'rectangle' || nodeShape === 'rounded'"
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
            v-for="shape in shapeOptions"
            :key="shape"
            class="nft-dropdown-item"
            :class="{ 'nft-dropdown-item--active': nodeShape === shape }"
            @click="handleNodeShapePick(shape)"
          >
            <I18nText :k="shapeLabels[shape]" />
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>

    <ElPopover
      v-if="!hideNodeFillAndBorder"
      v-model:visible="borderOpen"
      trigger="click"
      placement="bottom"
      :width="181"
      popper-class="node-floating-toolbar-popper"
    >
      <template #reference>
        <span class="nft-color-ref">
          <I18nTooltip
            k="canvas.floatingToolbar.borderColor"
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
          </I18nTooltip>
        </span>
      </template>
      <FloatingToolbarColorPicker
        :current-color="borderColor"
        :native-color="nativeBorderColor"
        @pick="pickColor('border', $event)"
      />
    </ElPopover>

    <ElPopover
      v-if="!hideNodeFillAndBorder"
      v-model:visible="fillOpen"
      trigger="click"
      placement="bottom"
      :width="181"
      popper-class="node-floating-toolbar-popper"
    >
      <template #reference>
        <span class="nft-color-ref">
          <I18nTooltip
            k="canvas.floatingToolbar.fillColor"
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
          </I18nTooltip>
        </span>
      </template>
      <FloatingToolbarColorPicker
        :current-color="backgroundColor"
        :native-color="nativeFillColor"
        @pick="pickColor('fill', $event)"
      />
    </ElPopover>
  </div>
</template>

<style src="./canvasToolbarMindMapNft.css"></style>
