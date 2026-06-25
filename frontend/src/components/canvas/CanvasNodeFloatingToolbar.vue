<script setup lang="ts">
/**
 * Frosted-glass floating toolbar anchored above the selected mind-map node.
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  ChevronDown,
  Minus,
  Square,
} from '@lucide/vue'

import MindMapSubgraphAiMark from './MindMapSubgraphAiMark.vue'

import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import { useLanguage } from '@/composables/core/useLanguage'
import { FLOATING_TOOLBAR_COLORS, FLOATING_TOOLBAR_FONT_SIZES } from '@/config/floatingToolbarColors'
import type { FloatingToolbarPosition } from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'
import { NODE_SHAPE_OPTIONS, type NodeShape } from '@/utils/nodeShapeStyle'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

const props = defineProps<{
  position: FloatingToolbarPosition
  nodeId: string | null
  aiGenerating?: boolean
  aiDisabled?: boolean
}>()

const emit = defineEmits<{
  aiSubgraphGenerate: []
}>()

const { t } = useLanguage()

const formatting = useCanvasToolbarFormatting({
  silentUpdates: true,
  pinnedNodeId: computed(() => props.nodeId),
})

const {
  fontFamily,
  fontSize,
  textColor,
  fontWeight,
  fontStyle,
  textDecoration,
  textAlign,
  backgroundColor,
  borderColor,
  nodeShape,
  handleToggleBold,
  handleToggleItalic,
  handleToggleUnderline,
  handleToggleStrikethrough,
  handleTextAlign,
  handleFontFamilyChange,
  handleFontSizePick,
  handleTextColorPick,
  handleFillColorPick,
  handleBorderColorPick,
  handleNodeShapePick,
} = formatting

const activeColorPanel = ref<'fill' | 'border' | 'text' | null>(null)
const typographyOpen = ref(false)

const toolbarStyle = computed(() => ({
  left: `${props.position.left}px`,
  top: `${props.position.top}px`,
  position: 'fixed' as const,
  zIndex: 5000,
}))

const fontOptions = computed(() => [
  { value: DIAGRAM_NODE_FONT_STACK, label: t('canvas.floatingToolbar.fontDefault') },
  { value: 'SimSun', label: t('canvas.floatingToolbar.fontSimSun') },
  { value: 'KaiTi', label: t('canvas.floatingToolbar.fontKaiTi') },
  { value: 'Inter', label: 'Inter' },
  { value: 'Space Grotesk', label: 'Space Grotesk' },
])

const shapeLabels: Record<NodeShape, string> = {
  rounded: 'canvas.floatingToolbar.shapeRounded',
  rectangle: 'canvas.floatingToolbar.shapeRectangle',
  oval: 'canvas.floatingToolbar.shapeOval',
  underline: 'canvas.floatingToolbar.shapeUnderline',
}

function toggleColorPanel(panel: 'fill' | 'border' | 'text') {
  activeColorPanel.value = activeColorPanel.value === panel ? null : panel
}

function pickColor(panel: 'fill' | 'border' | 'text', color: string) {
  if (panel === 'fill') handleFillColorPick(color)
  else if (panel === 'border') handleBorderColorPick(color)
  else handleTextColorPick(color)
  activeColorPanel.value = null
}

function onCustomColor(panel: 'fill' | 'border' | 'text', ev: Event) {
  const color = (ev.target as HTMLInputElement).value
  pickColor(panel, color)
}

function onShapePick(shape: NodeShape) {
  handleNodeShapePick(shape)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="position.visible"
      class="node-floating-toolbar pointer-events-auto"
      :style="toolbarStyle"
      @mousedown.stop
      @click.stop
    >
      <div class="node-floating-toolbar__inner">
        <!-- AI subgraph generation -->
        <button
          type="button"
          class="nft-btn nft-btn--ai"
          :class="{ 'nft-btn--ai-loading': aiGenerating }"
          :title="t('canvas.floatingToolbar.aiSubgraph')"
          :disabled="aiGenerating || aiDisabled"
          @click="emit('aiSubgraphGenerate')"
        >
          <MindMapSubgraphAiMark :loading="aiGenerating" />
        </button>

        <span class="nft-divider" />

        <!-- Shape selector -->
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
                @click="onShapePick(shape)"
              >
                {{ t(shapeLabels[shape]) }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <span class="nft-divider" />

        <!-- Fill color -->
        <div class="nft-color-wrap">
          <button
            type="button"
            class="nft-btn nft-btn--color"
            :title="t('canvas.floatingToolbar.fillColor')"
            @click="toggleColorPanel('fill')"
          >
            <span
              class="nft-color-swatch nft-color-swatch--fill"
              :style="{ backgroundColor: backgroundColor }"
            />
            <ChevronDown class="nft-chevron" />
          </button>
          <div
            v-if="activeColorPanel === 'fill'"
            class="nft-color-panel"
          >
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
          </div>
        </div>

        <!-- Border color -->
        <div class="nft-color-wrap">
          <button
            type="button"
            class="nft-btn nft-btn--color"
            :title="t('canvas.floatingToolbar.borderColor')"
            @click="toggleColorPanel('border')"
          >
            <span
              class="nft-color-swatch nft-color-swatch--ring"
              :style="{ borderColor: borderColor }"
            />
            <ChevronDown class="nft-chevron" />
          </button>
          <div
            v-if="activeColorPanel === 'border'"
            class="nft-color-panel"
          >
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
          </div>
        </div>

        <!-- Text color -->
        <div class="nft-color-wrap">
          <button
            type="button"
            class="nft-btn nft-btn--text-color"
            :title="t('canvas.floatingToolbar.textColor')"
            @click="toggleColorPanel('text')"
          >
            <span
              class="nft-text-a"
              :style="{ color: textColor }"
            >A</span>
            <ChevronDown class="nft-chevron" />
          </button>
          <div
            v-if="activeColorPanel === 'text'"
            class="nft-color-panel"
          >
            <div class="nft-color-grid">
              <button
                v-for="color in FLOATING_TOOLBAR_COLORS"
                :key="'text-' + color"
                type="button"
                class="nft-palette-swatch"
                :style="{ backgroundColor: color }"
                @click="pickColor('text', color)"
              />
            </div>
            <input
              type="color"
              class="nft-native-color"
              :value="textColor"
              @input="onCustomColor('text', $event)"
            />
          </div>
        </div>

        <span class="nft-divider" />

        <!-- Font size -->
        <ElDropdown
          trigger="click"
          placement="bottom-start"
          popper-class="node-floating-toolbar-popper"
        >
          <button
            type="button"
            class="nft-btn nft-btn--size"
          >
            <span>{{ fontSize }}</span>
            <ChevronDown class="nft-chevron" />
          </button>
          <template #dropdown>
            <ElDropdownMenu class="nft-dropdown-menu">
              <ElDropdownItem
                v-for="size in FLOATING_TOOLBAR_FONT_SIZES"
                :key="size"
                class="nft-dropdown-item"
                :class="{ 'nft-dropdown-item--active': fontSize === size }"
                @click="handleFontSizePick(size)"
              >
                {{ size }}px
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Typography drawer -->
        <ElDropdown
          v-model="typographyOpen"
          trigger="click"
          placement="bottom-start"
          popper-class="node-floating-toolbar-popper node-floating-toolbar-popper--wide"
        >
          <button
            type="button"
            class="nft-btn nft-btn--typography"
            :title="t('canvas.floatingToolbar.typography')"
          >
            <span
              class="nft-text-a nft-text-a--bold"
              :style="{ color: textColor }"
            >A</span>
            <span class="nft-align-lines">
              <span /><span /><span />
            </span>
            <ChevronDown class="nft-chevron" />
          </button>
          <template #dropdown>
            <ElDropdownMenu class="nft-dropdown-menu nft-dropdown-menu--wide">
              <ElDropdownItem class="nft-typography-dropdown-item">
                <div
                  class="nft-typography-panel"
                  @mousedown.stop
                  @click.stop
                >
                <div class="nft-typography-section">
                  <div class="nft-typography-label">{{ t('canvas.toolbar.alignLabel') }}</div>
                  <div class="nft-format-row">
                    <button
                      type="button"
                      class="nft-format-btn"
                      :class="{ 'nft-format-btn--active': textAlign === 'left' }"
                      @click.stop="handleTextAlign('left')"
                    >
                      <AlignLeft :size="14" />
                    </button>
                    <button
                      type="button"
                      class="nft-format-btn"
                      :class="{ 'nft-format-btn--active': textAlign === 'center' }"
                      @click.stop="handleTextAlign('center')"
                    >
                      <AlignCenter :size="14" />
                    </button>
                    <button
                      type="button"
                      class="nft-format-btn"
                      :class="{ 'nft-format-btn--active': textAlign === 'right' }"
                      @click.stop="handleTextAlign('right')"
                    >
                      <AlignRight :size="14" />
                    </button>
                  </div>
                </div>

                <div class="nft-typography-section">
                  <div class="nft-typography-label">{{ t('canvas.toolbar.formatLabel') }}</div>
                  <div class="nft-format-row nft-format-row--4">
                    <button
                      type="button"
                      class="nft-format-btn nft-format-btn--letter"
                      :class="{ 'nft-format-btn--active': fontWeight === 'bold' }"
                      @click.stop="handleToggleBold"
                    >
                      B
                    </button>
                    <button
                      type="button"
                      class="nft-format-btn nft-format-btn--letter italic"
                      :class="{ 'nft-format-btn--active': fontStyle === 'italic' }"
                      @click.stop="handleToggleItalic"
                    >
                      I
                    </button>
                    <button
                      type="button"
                      class="nft-format-btn nft-format-btn--letter underline"
                      :class="{ 'nft-format-btn--active': textDecoration?.includes('underline') }"
                      @click.stop="handleToggleUnderline"
                    >
                      U
                    </button>
                    <button
                      type="button"
                      class="nft-format-btn nft-format-btn--letter line-through"
                      :class="{ 'nft-format-btn--active': textDecoration?.includes('line-through') }"
                      @click.stop="handleToggleStrikethrough"
                    >
                      S
                    </button>
                  </div>
                </div>

                <div class="nft-typography-section">
                  <div class="nft-typography-label">{{ t('canvas.toolbar.fontLabel') }}</div>
                  <select
                    :value="fontFamily"
                    class="nft-font-select"
                    @change="handleFontFamilyChange"
                  >
                    <option
                      v-for="opt in fontOptions"
                      :key="opt.value"
                      :value="opt.value"
                    >
                      {{ opt.label }}
                    </option>
                  </select>
                </div>
                </div>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.node-floating-toolbar {
  position: fixed;
  z-index: 5000;
  transform: translate(-50%, -100%);
}

.node-floating-toolbar__inner {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 8px;
  border-radius: 9999px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  box-shadow:
    0 4px 16px rgba(15, 23, 42, 0.1),
    0 1px 3px rgba(15, 23, 42, 0.06);
}

.nft-btn {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 28px;
  padding: 0 6px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #334155;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  transition: background 0.15s;
}

.nft-btn:hover {
  background: rgba(241, 245, 249, 0.9);
}

.nft-btn--ai {
  padding: 0 8px 0 7px;
  gap: 0;
}

.nft-btn--ai:hover:not(:disabled) :deep(.mg-subgraph-ai-mark__letters) {
  filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.38));
}

.nft-btn--ai:hover:not(:disabled) :deep(.mg-subgraph-ai-mark__sparkles:not(.mg-subgraph-ai-mark__sparkles--spin)) {
  color: #7c3aed;
  transform: scale(1.08) rotate(-6deg);
  filter: drop-shadow(0 0 6px rgba(124, 58, 237, 0.55));
}

.nft-btn--ai:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.nft-btn--ai-loading {
  opacity: 1;
}

.nft-btn--ai:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(239, 246, 255, 0.98) 0%,
    rgba(237, 233, 254, 0.95) 55%,
    rgba(252, 231, 243, 0.92) 100%
  );
}

.nft-btn--size {
  min-width: 40px;
  justify-content: center;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.nft-btn--typography {
  gap: 4px;
  padding-right: 4px;
}

.nft-icon {
  width: 16px;
  height: 16px;
}

.nft-chevron {
  width: 12px;
  height: 12px;
  color: #94a3b8;
  flex-shrink: 0;
}

.nft-divider {
  width: 1px;
  height: 18px;
  margin: 0 2px;
  background: #e2e8f0;
  flex-shrink: 0;
}

.nft-color-wrap {
  position: relative;
}

.nft-color-swatch {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
}

.nft-color-swatch--fill {
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.nft-color-swatch--ring {
  background: transparent;
  border: 2.5px solid currentColor;
}

.nft-text-a {
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  border-bottom: 2.5px solid currentColor;
  padding-bottom: 1px;
}

.nft-text-a--bold {
  font-size: 14px;
}

.nft-shape-oval {
  display: block;
  width: 18px;
  height: 12px;
  border: 1.5px solid #334155;
  border-radius: 9999px;
}

.nft-align-lines {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 12px;
}

.nft-align-lines span {
  display: block;
  height: 1.5px;
  background: #334155;
  border-radius: 1px;
}

.nft-align-lines span:nth-child(1) {
  width: 100%;
}
.nft-align-lines span:nth-child(2) {
  width: 75%;
}
.nft-align-lines span:nth-child(3) {
  width: 50%;
}

.nft-color-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 8px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  z-index: 5010;
  min-width: 160px;
}

.nft-color-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  margin-bottom: 6px;
}

.nft-palette-swatch {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
  padding: 0;
}

.nft-palette-swatch:hover {
  transform: scale(1.08);
}

.nft-native-color {
  width: 100%;
  height: 28px;
  border: none;
  padding: 0;
  cursor: pointer;
}

.nft-shape-option,
.nft-size-option {
  display: block;
  width: 100%;
  padding: 6px 14px;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
}

.nft-shape-option:hover,
.nft-size-option:hover {
  background: #f1f5f9;
}

.nft-shape-option--active,
.nft-size-option--active {
  color: #2563eb;
  font-weight: 600;
}

.nft-typography-panel {
  padding: 10px 12px;
  min-width: 200px;
}

.nft-typography-section + .nft-typography-section {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
}

.nft-typography-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
  margin-bottom: 6px;
}

.nft-format-row {
  display: flex;
  gap: 4px;
}

.nft-format-row--4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}

.nft-format-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.nft-format-btn:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.nft-format-btn--active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
}

.nft-font-select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
  color: #334155;
}
</style>

<style>
.node-floating-toolbar-popper.el-popper {
  z-index: 5100 !important;
  padding: 4px !important;
  border-radius: 10px !important;
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12) !important;
}

.node-floating-toolbar-popper .nft-dropdown-menu {
  padding: 0 !important;
  min-width: 0 !important;
  list-style: none !important;
}

.node-floating-toolbar-popper .el-dropdown-menu {
  list-style: none !important;
  padding: 0 !important;
  margin: 0 !important;
}

.node-floating-toolbar-popper .nft-dropdown-menu--wide {
  min-width: 220px !important;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-dropdown-item {
  padding: 6px 12px !important;
  font-size: 13px;
  line-height: 1.4;
  color: #334155;
  justify-content: flex-start !important;
  list-style: none !important;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-dropdown-item::before,
.node-floating-toolbar-popper .el-dropdown-menu__item.nft-dropdown-item::marker {
  content: none !important;
  display: none !important;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-dropdown-item:hover {
  background: #f1f5f9 !important;
  color: #334155 !important;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-dropdown-item--active {
  color: #2563eb !important;
  font-weight: 600;
  background: transparent !important;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-typography-dropdown-item {
  padding: 0 !important;
  height: auto;
  line-height: normal;
  cursor: default;
}

.node-floating-toolbar-popper .el-dropdown-menu__item.nft-typography-dropdown-item:hover {
  background: transparent !important;
  color: inherit !important;
}

.node-floating-toolbar-popper--wide.el-popper {
  min-width: 220px;
}
</style>
