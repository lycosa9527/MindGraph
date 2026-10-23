<script setup lang="ts">
/**
 * Frosted-glass floating toolbar anchored above the selected mind-map node.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  ChevronDown,
  Lightbulb,
  Minus,
  Square,
} from '@lucide/vue'

import { CANVAS_NODE_CHROME_Z } from '@/components/common/swissGlassStack'
import { useCanvasToolbarFormatting } from '@/composables/canvasToolbar'
import type {
  FloatingToolbarPosition,
  FloatingToolbarSize,
} from '@/composables/canvasToolbar/useNodeFloatingToolbarPosition'
import { useCollabGuestAiGate } from '@/composables/collab/useCollabGuestAiGate'
import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useLearningAiGate } from '@/composables/learningSpace/useLearningAiGate'
import { useNodeExplainEditGate } from '@/composables/mindMap/nodeExplainEditGate'
import { diagramPaintFontFamily, ensureDiagramCanvasFonts } from '@/fonts/diagramCanvasFonts'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import { retainEditOnExplainPointer } from '@/utils/nodeExplainTrigger'
import { NODE_SHAPE_OPTIONS, type NodeShape } from '@/utils/nodeShapeStyle'
import { createToolbarPointerAction } from '@/utils/toolbarPointerAction'

import FloatingToolbarColorPicker from './FloatingToolbarColorPicker.vue'
import MindMapSubgraphAiMark from './MindMapSubgraphAiMark.vue'

const props = defineProps<{
  position: FloatingToolbarPosition
  nodeId: string | null
  aiGenerating?: boolean
  aiDisabled?: boolean
  showAiSubgraph?: boolean
}>()

const emit = defineEmits<{
  aiSubgraphGenerate: []
  explainNode: []
  sizeChange: [size: FloatingToolbarSize | null]
}>()

const rootEl = ref<HTMLElement | null>(null)
const diagramStore = useDiagramSession()
const hideNodeShape = computed(() => {
  const nodeId = props.nodeId
  if (!nodeId) return false
  const node = diagramStore.data?.nodes?.find((item) => item.id === nodeId)
  return node?.type === 'boundary' || node?.type === 'label'
})
let sizeObserver: ResizeObserver | null = null

function publishSize(el: HTMLElement | null): void {
  if (!el) {
    emit('sizeChange', null)
    return
  }
  const rect = el.getBoundingClientRect()
  if (rect.width < 1 || rect.height < 1) {
    emit('sizeChange', null)
    return
  }
  emit('sizeChange', { width: rect.width, height: rect.height })
}

watch(
  rootEl,
  (el) => {
    sizeObserver?.disconnect()
    sizeObserver = null
    if (!el) {
      publishSize(null)
      return
    }
    publishSize(el)
    sizeObserver = new ResizeObserver(() => publishSize(el))
    sizeObserver.observe(el)
  },
  { flush: 'post' }
)

onUnmounted(() => {
  sizeObserver?.disconnect()
  sizeObserver = null
  emit('sizeChange', null)
})

const { t } = useLanguage()
const { showCanvasAiFeatures } = useLearningAiGate()
const { aiBlockedByCollab, notifyCollabGuestAiBlocked } = useCollabGuestAiGate()
const { locked: explainLockedUntilConfirm } = useNodeExplainEditGate()
const guestAiDisabled = computed(() => Boolean(props.aiDisabled) || aiBlockedByCollab.value)
const explainTitle = computed(() => {
  if (explainLockedUntilConfirm.value) return t('canvas.floatingToolbar.explainNeedsConfirm')
  if (aiBlockedByCollab.value) return t('canvas.toolbar.collabAiBlocked')
  return t('canvas.floatingToolbar.explain')
})

const formatting = useCanvasToolbarFormatting({
  silentUpdates: true,
  pinnedNodeId: computed(() => props.nodeId),
})

const {
  fontFamily,
  fontSize,
  fontSizeChoices,
  textColor,
  fontWeight,
  fontStyle,
  textDecoration,
  textAlign,
  backgroundColor,
  nativeFillColor,
  borderColor,
  nativeBorderColor,
  nativeTextColor,
  nodeShape,
  handleToggleBold,
  handleToggleItalic,
  handleToggleUnderline,
  handleToggleStrikethrough,
  handleTextAlign,
  handleFontFamilyPick,
  handleFontSizePick,
  handleTextColorPick,
  handleFillColorPick,
  handleBorderColorPick,
  handleNodeShapePick,
} = formatting

const activeColorPanel = ref<'fill' | 'border' | 'text' | null>(null)
const typographyOpen = ref(false)

watch(typographyOpen, (open) => {
  if (!open) return
  void ensureDiagramCanvasFonts(['SimSun', 'KaiTi', 'Inter', 'Space Grotesk'])
})

const aiSubgraphVisible = computed(
  () => showCanvasAiFeatures.value && props.showAiSubgraph === true
)

function onAiSubgraphClick(): void {
  if (guestAiDisabled.value) {
    notifyCollabGuestAiBlocked()
    return
  }
  emit('aiSubgraphGenerate')
}

function onExplainPointerDown(event: PointerEvent): void {
  retainEditOnExplainPointer(event, explainLockedUntilConfirm.value)
}

function onExplainClick(): void {
  if (explainLockedUntilConfirm.value) return
  if (aiBlockedByCollab.value) {
    notifyCollabGuestAiBlocked()
    return
  }
  emit('explainNode')
}

const toolbarStyle = computed(() => ({
  left: `${props.position.left}px`,
  top: `${props.position.top}px`,
  position: 'fixed' as const,
  zIndex: CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR,
  // above: anchor is bar bottom; below: anchor is bar top (fit-to-screen flip).
  transform: props.position.placement === 'below' ? 'translate(-50%, 0)' : 'translate(-50%, -100%)',
}))

const fontOptions = computed(() => [
  {
    value: DIAGRAM_NODE_FONT_STACK,
    label: t('canvas.floatingToolbar.fontDefault'),
    labelKey: 'canvas.floatingToolbar.fontDefault',
  },
  {
    value: 'SimSun',
    label: t('canvas.floatingToolbar.fontSimSun'),
    labelKey: 'canvas.floatingToolbar.fontSimSun',
  },
  {
    value: 'KaiTi',
    label: t('canvas.floatingToolbar.fontKaiTi'),
    labelKey: 'canvas.floatingToolbar.fontKaiTi',
  },
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

function onShapePick(shape: NodeShape) {
  handleNodeShapePick(shape)
}

function isActiveFontSize(size: number): boolean {
  return Math.round(Number(fontSize.value)) === size
}

const typographyPointer = createToolbarPointerAction()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="position.visible"
      ref="rootEl"
      class="node-floating-toolbar pointer-events-auto"
      :style="toolbarStyle"
      @mousedown.stop
      @click.stop
    >
      <div class="node-floating-toolbar__inner">
        <!-- AI subgraph generation (branch / child nodes only; hidden on central topic) -->
        <button
          v-if="aiSubgraphVisible"
          type="button"
          class="nft-btn nft-btn--ai"
          :class="{
            'nft-btn--ai-loading': aiGenerating,
            'nft-btn--ai-blocked': guestAiDisabled && !aiGenerating,
          }"
          :title="
            guestAiDisabled
              ? t('canvas.toolbar.collabAiBlocked')
              : t('canvas.floatingToolbar.aiSubgraph')
          "
          :aria-disabled="guestAiDisabled"
          :disabled="aiGenerating"
          @click="onAiSubgraphClick"
        >
          <MindMapSubgraphAiMark :loading="aiGenerating" />
        </button>

        <span
          v-if="aiSubgraphVisible"
          class="nft-divider"
        />

        <!-- Shape selector. Boundary rings and dimension labels stay unshaped. -->
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
                v-for="shape in NODE_SHAPE_OPTIONS"
                :key="shape"
                class="nft-dropdown-item"
                :class="{ 'nft-dropdown-item--active': nodeShape === shape }"
                @click="onShapePick(shape)"
              >
                <I18nText :k="shapeLabels[shape]" />
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
            <FloatingToolbarColorPicker
              :current-color="backgroundColor"
              :native-color="nativeFillColor"
              @pick="pickColor('fill', $event)"
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
            <FloatingToolbarColorPicker
              :current-color="borderColor"
              :native-color="nativeBorderColor"
              @pick="pickColor('border', $event)"
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
              >A</span
            >
            <ChevronDown class="nft-chevron" />
          </button>
          <div
            v-if="activeColorPanel === 'text'"
            class="nft-color-panel"
          >
            <FloatingToolbarColorPicker
              :current-color="textColor"
              :native-color="nativeTextColor"
              @pick="pickColor('text', $event)"
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
                v-for="size in fontSizeChoices"
                :key="size"
                class="nft-dropdown-item"
                :class="{ 'nft-dropdown-item--active': isActiveFontSize(size) }"
              >
                <button
                  type="button"
                  class="nft-size-option"
                  @pointerdown.stop
                  @pointerup.stop="
                    typographyPointer.onPointerUp($event, () => handleFontSizePick(size))
                  "
                  @click="typographyPointer.onClick(() => handleFontSizePick(size))"
                >
                  {{ size }}px
                </button>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Typography drawer -->
        <ElDropdown
          v-model="typographyOpen"
          trigger="click"
          :hide-on-click="false"
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
              >A</span
            >
            <span class="nft-align-lines"> <span /><span /><span /> </span>
            <ChevronDown class="nft-chevron" />
          </button>
          <template #dropdown>
            <ElDropdownMenu class="nft-dropdown-menu nft-dropdown-menu--wide">
              <ElDropdownItem class="nft-typography-dropdown-item">
                <div
                  class="nft-typography-panel"
                  @pointerdown.stop
                  @mousedown.stop
                  @click.stop
                >
                  <div class="nft-typography-section">
                    <div class="nft-typography-label">
                      <I18nText k="canvas.toolbar.alignLabel" />
                    </div>
                    <div class="nft-format-row">
                      <button
                        type="button"
                        class="nft-format-btn"
                        :class="{ 'nft-format-btn--active': textAlign === 'left' }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, () => handleTextAlign('left'))
                        "
                        @click.stop="typographyPointer.onClick(() => handleTextAlign('left'))"
                      >
                        <AlignLeft :size="14" />
                      </button>
                      <button
                        type="button"
                        class="nft-format-btn"
                        :class="{ 'nft-format-btn--active': textAlign === 'center' }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, () => handleTextAlign('center'))
                        "
                        @click.stop="typographyPointer.onClick(() => handleTextAlign('center'))"
                      >
                        <AlignCenter :size="14" />
                      </button>
                      <button
                        type="button"
                        class="nft-format-btn"
                        :class="{ 'nft-format-btn--active': textAlign === 'right' }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, () => handleTextAlign('right'))
                        "
                        @click.stop="typographyPointer.onClick(() => handleTextAlign('right'))"
                      >
                        <AlignRight :size="14" />
                      </button>
                    </div>
                  </div>

                  <div class="nft-typography-section">
                    <div class="nft-typography-label">
                      <I18nText k="canvas.toolbar.formatLabel" />
                    </div>
                    <div class="nft-format-row nft-format-row--4">
                      <button
                        type="button"
                        class="nft-format-btn nft-format-btn--letter"
                        :class="{ 'nft-format-btn--active': fontWeight === 'bold' }"
                        @pointerdown.stop
                        @pointerup.stop="typographyPointer.onPointerUp($event, handleToggleBold)"
                        @click.stop="typographyPointer.onClick(handleToggleBold)"
                      >
                        B
                      </button>
                      <button
                        type="button"
                        class="nft-format-btn nft-format-btn--letter italic"
                        :class="{ 'nft-format-btn--active': fontStyle === 'italic' }"
                        @pointerdown.stop
                        @pointerup.stop="typographyPointer.onPointerUp($event, handleToggleItalic)"
                        @click.stop="typographyPointer.onClick(handleToggleItalic)"
                      >
                        I
                      </button>
                      <button
                        type="button"
                        class="nft-format-btn nft-format-btn--letter underline"
                        :class="{ 'nft-format-btn--active': textDecoration?.includes('underline') }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, handleToggleUnderline)
                        "
                        @click.stop="typographyPointer.onClick(handleToggleUnderline)"
                      >
                        U
                      </button>
                      <button
                        type="button"
                        class="nft-format-btn nft-format-btn--letter line-through"
                        :class="{
                          'nft-format-btn--active': textDecoration?.includes('line-through'),
                        }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, handleToggleStrikethrough)
                        "
                        @click.stop="typographyPointer.onClick(handleToggleStrikethrough)"
                      >
                        S
                      </button>
                    </div>
                  </div>

                  <div class="nft-typography-section">
                    <div class="nft-typography-label">
                      <I18nText k="canvas.toolbar.fontLabel" />
                    </div>
                    <div
                      class="nft-font-options"
                      role="listbox"
                      :aria-label="t('canvas.toolbar.fontLabel')"
                    >
                      <button
                        v-for="opt in fontOptions"
                        :key="opt.value"
                        type="button"
                        class="nft-font-option"
                        role="option"
                        :aria-selected="fontFamily === opt.value"
                        :class="{ 'nft-font-option--active': fontFamily === opt.value }"
                        :style="{
                          fontFamily: diagramPaintFontFamily(opt.value, DIAGRAM_NODE_FONT_STACK),
                        }"
                        @pointerdown.stop
                        @pointerup.stop="
                          typographyPointer.onPointerUp($event, () =>
                            handleFontFamilyPick(opt.value)
                          )
                        "
                        @click.stop="
                          typographyPointer.onClick(() => handleFontFamilyPick(opt.value))
                        "
                      >
                        {{ opt.label }}
                      </button>
                    </div>
                  </div>
                </div>
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>

        <!-- Node explanation (Kitty) -->
        <button
          v-if="showCanvasAiFeatures"
          type="button"
          class="nft-btn nft-btn--explain"
          :class="{
            'nft-btn--explain-blocked': aiBlockedByCollab || explainLockedUntilConfirm,
          }"
          data-node-explain-trigger
          :title="explainTitle"
          :disabled="!nodeId"
          :aria-disabled="aiBlockedByCollab || explainLockedUntilConfirm"
          @pointerdown="onExplainPointerDown"
          @click="onExplainClick"
        >
          <Lightbulb
            class="nft-icon nft-icon--explain"
            :stroke-width="1.75"
          />
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.node-floating-toolbar {
  position: fixed;
  /* Keep in sync with CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR */
  z-index: 5000;
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

.nft-btn--ai:hover:not(:disabled)
  :deep(.mg-subgraph-ai-mark__sparkles:not(.mg-subgraph-ai-mark__sparkles--spin)) {
  color: #7c3aed;
  transform: scale(1.08) rotate(-6deg);
  filter: drop-shadow(0 0 6px rgba(124, 58, 237, 0.55));
}

.nft-btn--ai:disabled,
.nft-btn--ai-blocked,
.nft-btn--explain-blocked {
  opacity: 0.45;
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

.nft-btn--explain {
  color: #d97706;
}

.nft-btn--explain:hover:not(:disabled):not(.nft-btn--explain-blocked) {
  background: rgba(254, 243, 199, 0.9);
  color: #b45309;
}

.nft-btn--explain:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.nft-icon {
  width: 16px;
  height: 16px;
}

.nft-icon--explain {
  fill: rgba(251, 191, 36, 0.22);
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
  /* Keep in sync with CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR_PANEL */
  z-index: 5010;
  min-width: 160px;
}

.nft-shape-option,
.nft-size-option {
  display: block;
  width: 100%;
  padding: 8px 14px;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 15px;
  color: inherit;
  cursor: pointer;
  touch-action: manipulation;
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
  touch-action: manipulation;
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
  min-width: 40px;
  height: 40px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  touch-action: manipulation;
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

.nft-font-options {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nft-font-option {
  display: block;
  width: 100%;
  text-align: start;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #fff;
  font-size: 16px;
  line-height: 1.3;
  color: #334155;
  cursor: pointer;
  touch-action: manipulation;
}

.nft-font-option--active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
}
</style>

<style>
.node-floating-toolbar-popper.el-popper {
  /* Keep in sync with CANVAS_NODE_CHROME_Z.FLOATING_TOOLBAR_POPPER */
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
