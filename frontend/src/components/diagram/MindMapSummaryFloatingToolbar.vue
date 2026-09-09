<script setup lang="ts">
/**
 * Property card for a mind-map summary brace (type, line, color, thickness).
 */
import { computed, ref } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { ChevronDown } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { FLOATING_TOOLBAR_COLORS } from '@/config/floatingToolbarColors'
import type {
  MindMapSummaryChromePatch,
  MindMapSummaryKind,
  MindMapSummaryLineStyle,
} from '@/types'
import {
  MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH,
  MINDMAP_SUMMARY_KINDS,
  MINDMAP_SUMMARY_LINE_STYLES,
  MINDMAP_SUMMARY_STROKE_WIDTH_MAX,
  MINDMAP_SUMMARY_STROKE_WIDTH_MIN,
  parseMindMapSummaryStrokeColor,
  readMindMapSummaries,
  resolveMindMapSummaryKind,
  resolveMindMapSummaryLineStyle,
  resolveMindMapSummaryStrokeWidth,
} from '@/utils/mindMapSummary'

const KIND_GLYPH: Record<MindMapSummaryKind, string> = {
  brace: '{',
  bracket: '[',
  paren: '(',
}

const LINE_DASH: Record<MindMapSummaryLineStyle, string | undefined> = {
  solid: undefined,
  dashed: '5 4',
  dotted: '1.5 3',
}

const SUMMARY_COLORS = ['#c2410c', ...FLOATING_TOOLBAR_COLORS.filter((c) => c !== '#c2410c')]

const props = defineProps<{
  summaryId: string
  left: number
  top: number
  themeStroke: string
}>()

const { t } = useLanguage()
const diagramStore = useDiagramSession()
const colorOpen = ref(false)

const spec = computed(() =>
  readMindMapSummaries(diagramStore.data).find((item) => item.id === props.summaryId)
)

const kind = computed(() => (spec.value ? resolveMindMapSummaryKind(spec.value) : 'brace'))
const lineStyle = computed(() =>
  spec.value ? resolveMindMapSummaryLineStyle(spec.value) : 'solid'
)
const strokeColor = computed(() => spec.value?.strokeColor ?? props.themeStroke)
const strokeWidth = computed(() =>
  spec.value ? resolveMindMapSummaryStrokeWidth(spec.value) : MINDMAP_SUMMARY_DEFAULT_STROKE_WIDTH
)

const toolbarStyle = computed(() => ({
  left: `${props.left}px`,
  top: `${props.top}px`,
}))

const kindLabel: Record<MindMapSummaryKind, string> = {
  brace: 'canvas.floatingToolbar.summaryKindBrace',
  bracket: 'canvas.floatingToolbar.summaryKindBracket',
  paren: 'canvas.floatingToolbar.summaryKindParen',
}

const lineLabel: Record<MindMapSummaryLineStyle, string> = {
  solid: 'canvas.floatingToolbar.summaryLineSolid',
  dashed: 'canvas.floatingToolbar.summaryLineDashed',
  dotted: 'canvas.floatingToolbar.summaryLineDotted',
}

function applyChrome(patch: MindMapSummaryChromePatch): void {
  diagramStore.updateMindMapSummaryChrome(props.summaryId, patch)
}

function onKindPick(next: MindMapSummaryKind): void {
  applyChrome({ kind: next })
}

function onLineStylePick(next: MindMapSummaryLineStyle): void {
  applyChrome({ lineStyle: next })
}

function onColorPick(color: string): void {
  const parsed = parseMindMapSummaryStrokeColor(color)
  if (!parsed) return
  applyChrome({ strokeColor: parsed })
  colorOpen.value = false
}

function onCustomColor(event: Event): void {
  onColorPick((event.target as HTMLInputElement).value)
}

function bumpWidth(delta: number): void {
  const next = Math.min(
    MINDMAP_SUMMARY_STROKE_WIDTH_MAX,
    Math.max(MINDMAP_SUMMARY_STROKE_WIDTH_MIN, strokeWidth.value + delta)
  )
  applyChrome({ strokeWidth: next })
}

function toggleColor(): void {
  colorOpen.value = !colorOpen.value
}
</script>

<template>
  <Teleport to="body">
    <div
      class="mm-summary-toolbar"
      :style="toolbarStyle"
      role="dialog"
      :aria-label="t('canvas.floatingToolbar.summaryStyle')"
      @pointerdown.stop
      @mousedown.stop
      @click.stop
    >
      <div class="mm-summary-toolbar__row">
        <span class="mm-summary-toolbar__label">{{ t('canvas.floatingToolbar.summaryType') }}</span>
        <ElDropdown
          trigger="click"
          placement="bottom-end"
          popper-class="mm-summary-toolbar-popper"
        >
          <button
            type="button"
            class="mm-summary-toolbar__field"
            :title="t(kindLabel[kind])"
          >
            <span class="mm-summary-toolbar__glyph">{{ KIND_GLYPH[kind] }}</span>
            <ChevronDown class="mm-summary-toolbar__chevron" />
          </button>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem
                v-for="option in MINDMAP_SUMMARY_KINDS"
                :key="option"
                :class="{ 'is-active': kind === option }"
                @click="onKindPick(option)"
              >
                <span class="mm-summary-toolbar__glyph">{{ KIND_GLYPH[option] }}</span>
                {{ t(kindLabel[option]) }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>

      <div class="mm-summary-toolbar__row">
        <span class="mm-summary-toolbar__label">{{ t('canvas.floatingToolbar.summaryLine') }}</span>
        <div class="mm-summary-toolbar__pair">
          <ElDropdown
            trigger="click"
            placement="bottom-end"
            popper-class="mm-summary-toolbar-popper"
          >
            <button
              type="button"
              class="mm-summary-toolbar__field mm-summary-toolbar__field--half"
              :title="t(lineLabel[lineStyle])"
            >
              <svg
                class="mm-summary-toolbar__line"
                viewBox="0 0 28 10"
                aria-hidden="true"
              >
                <line
                  x1="2"
                  y1="5"
                  x2="26"
                  y2="5"
                  :stroke="strokeColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  :stroke-dasharray="LINE_DASH[lineStyle]"
                />
              </svg>
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  v-for="option in MINDMAP_SUMMARY_LINE_STYLES"
                  :key="option"
                  :class="{ 'is-active': lineStyle === option }"
                  @click="onLineStylePick(option)"
                >
                  <svg
                    class="mm-summary-toolbar__line"
                    viewBox="0 0 28 10"
                    aria-hidden="true"
                  >
                    <line
                      x1="2"
                      y1="5"
                      x2="26"
                      y2="5"
                      stroke="#334155"
                      stroke-width="2"
                      stroke-linecap="round"
                      :stroke-dasharray="LINE_DASH[option]"
                    />
                  </svg>
                  {{ t(lineLabel[option]) }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>

          <div class="mm-summary-toolbar__color-wrap">
            <button
              type="button"
              class="mm-summary-toolbar__field mm-summary-toolbar__field--half"
              :title="t('canvas.floatingToolbar.borderColor')"
              @click="toggleColor"
            >
              <span
                class="mm-summary-toolbar__swatch"
                :style="{ backgroundColor: strokeColor }"
              />
              <ChevronDown class="mm-summary-toolbar__chevron" />
            </button>
            <div
              v-if="colorOpen"
              class="mm-summary-toolbar__palette"
            >
              <button
                v-for="color in SUMMARY_COLORS"
                :key="color"
                type="button"
                class="mm-summary-toolbar__swatch-btn"
                :style="{ backgroundColor: color }"
                @click="onColorPick(color)"
              />
              <input
                type="color"
                class="mm-summary-toolbar__native"
                :value="strokeColor"
                @input="onCustomColor"
              >
            </div>
          </div>
        </div>
      </div>

      <div class="mm-summary-toolbar__row">
        <span class="mm-summary-toolbar__label mm-summary-toolbar__label--spacer" />
        <div
          class="mm-summary-toolbar__stepper"
          :title="t('canvas.floatingToolbar.summaryThickness')"
        >
          <span class="mm-summary-toolbar__px">{{ strokeWidth }}px</span>
          <div class="mm-summary-toolbar__stepper-btns">
            <button
              type="button"
              class="mm-summary-toolbar__step"
              :disabled="strokeWidth >= MINDMAP_SUMMARY_STROKE_WIDTH_MAX"
              :aria-label="t('canvas.floatingToolbar.summaryThickness')"
              @click="bumpWidth(1)"
            >
              ▲
            </button>
            <button
              type="button"
              class="mm-summary-toolbar__step"
              :disabled="strokeWidth <= MINDMAP_SUMMARY_STROKE_WIDTH_MIN"
              :aria-label="t('canvas.floatingToolbar.summaryThickness')"
              @click="bumpWidth(-1)"
            >
              ▼
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mm-summary-toolbar {
  position: fixed;
  z-index: 5010;
  min-width: 248px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #ececec;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mm-summary-toolbar__row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mm-summary-toolbar__label {
  flex: 0 0 64px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.2;
}

.mm-summary-toolbar__label--spacer {
  visibility: hidden;
}

.mm-summary-toolbar__pair {
  flex: 1;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.mm-summary-toolbar__row :deep(.el-dropdown) {
  flex: 1;
  min-width: 0;
}

.mm-summary-toolbar__field,
.mm-summary-toolbar__stepper {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #d4d4d8;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
}

.mm-summary-toolbar__field--half {
  width: 76px;
  flex: 1;
}

.mm-summary-toolbar__glyph {
  font-size: 18px;
  font-weight: 500;
  line-height: 1;
}

.mm-summary-toolbar__chevron {
  width: 14px;
  height: 14px;
  color: #94a3b8;
  flex-shrink: 0;
}

.mm-summary-toolbar__line {
  width: 28px;
  height: 10px;
}

.mm-summary-toolbar__swatch {
  display: block;
  width: 28px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.mm-summary-toolbar__color-wrap {
  position: relative;
  flex: 1;
}

.mm-summary-toolbar__palette {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  width: 168px;
  padding: 8px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}

.mm-summary-toolbar__swatch-btn {
  width: 20px;
  height: 20px;
  padding: 0;
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  cursor: pointer;
}

.mm-summary-toolbar__native {
  grid-column: 1 / -1;
  width: 100%;
  height: 26px;
  padding: 0;
  border: none;
  cursor: pointer;
}

.mm-summary-toolbar__px {
  font-size: 13px;
  color: #334155;
}

.mm-summary-toolbar__stepper-btns {
  display: flex;
  flex-direction: column;
  margin-right: -4px;
}

.mm-summary-toolbar__step {
  padding: 0 2px;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 8px;
  line-height: 1;
  cursor: pointer;
}

.mm-summary-toolbar__step:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>

<style>
.mm-summary-toolbar-popper .el-dropdown-menu__item.is-active {
  color: #2563eb;
  font-weight: 600;
}
</style>
